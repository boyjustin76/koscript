# -*- coding: utf-8 -*-
"""Find and run the poppler command-line tools.

Why a module and not two lines of ``subprocess``:

**1. The binaries are not on PATH on Windows.** ``winget install
oschwartz10612.Poppler`` drops them in a versioned folder under
``%LOCALAPPDATA%\\Microsoft\\WinGet\\Packages``, so code that just calls
``pdftotext`` works on the author's Linux box and raises ``FileNotFoundError``
on every Windows machine. That path is the ``x`` here -- put it in
``KOSCRIPT_POPPLER`` and nothing below has to guess.

**2. The ``pdftotext`` on PATH may not be poppler at all.** Xpdf ships a program
with the same name, and Git for Windows puts one in ``/mingw64/bin``. It is not a
drop-in: its ``-layout`` lays the page out differently, which moves every
indent -- and indent is how :mod:`koscript.pdfform.prompter` tells a wrapped line
from a new paragraph. So candidates are identified by their ``-v`` banner and a
real poppler wins, whatever the PATH order says. :func:`banner` tells you which
one you got.

**3. Xpdf's ``pdftotext`` silently drops every non-ASCII character** unless you
pass ``-enc UTF-8``. No warning, exit status 0: a Korean script comes out as the
punctuation between the words. :func:`text` always passes the flag; poppler
ignores it.

Nothing in this module parses a PDF. Poppler does that; we only locate it, run
it, and hand back bytes or text.
"""
import glob
import os
import re
import subprocess

#: Set this to the folder holding ``pdftotext``/``pdftoppm``/... if it is not on PATH.
ENV = 'KOSCRIPT_POPPLER'

_found = {}
_banner = {}


def banner(name):
    """First line of the binary's ``-v`` output -- which program you actually got."""
    return _banner.get(tool(name), '')


class PopplerMissing(RuntimeError):
    """Raised with install instructions, because "FileNotFoundError" teaches nobody."""


def _exe(name):
    return name + '.exe' if os.name == 'nt' else name


def _candidates(name):
    exe = _exe(name)
    for var in (ENV, 'POPPLER_BIN'):         # POPPLER_BIN is the older spelling
        here = os.environ.get(var)
        if here:
            yield os.path.join(here, exe)
    yield name                               # on PATH
    local = os.environ.get('LOCALAPPDATA', '')
    if local:                                # winget, Windows
        for p in sorted(glob.glob(os.path.join(
                local, 'Microsoft', 'WinGet', 'Packages',
                '*oppler*', '*', 'Library', 'bin', exe)), reverse=True):
            yield p
    home = os.environ.get('USERPROFILE', '')
    if home:                                 # scoop, Windows
        for p in sorted(glob.glob(os.path.join(
                home, 'scoop', 'apps', 'poppler', '*', 'bin', exe)), reverse=True):
            yield p
    for p in ('/usr/bin', '/usr/local/bin', '/opt/homebrew/bin'):
        yield os.path.join(p, exe)


def tool(name):
    """Path of a working binary called ``name``, preferring a real poppler.

    Every candidate is asked for its ``-v`` banner. A poppler build is taken
    straight away; anything else (Xpdf, most likely) is remembered as a fallback
    and used only if no poppler turns up.
    """
    if name in _found:
        return _found[name]
    fallback = None
    for cand in _candidates(name):
        try:
            got = subprocess.run([cand, '-v'], capture_output=True)
        except OSError:
            continue
        said = (got.stdout + got.stderr).decode('utf-8', 'ignore')
        if 'poppler' in said.lower():
            _found[name] = cand
            _banner[cand] = said.strip().splitlines()[0] if said.strip() else ''
            return cand
        if fallback is None:
            fallback = (cand, said)
    if fallback:
        _found[name] = fallback[0]
        _banner[fallback[0]] = (fallback[1].strip().splitlines() or [''])[0]
        return fallback[0]
    raise PopplerMissing(
        '%s not found. Install poppler and, if it is not on PATH, point %s at its bin folder.\n'
        '  Windows: winget install oschwartz10612.Poppler\n'
        '  macOS:   brew install poppler\n'
        '  Debian:  apt install poppler-utils' % (name, ENV))


def run(name, args, binary=False):
    """Run a poppler tool. Returns stdout as ``str`` (utf-8, lossy) or ``bytes``.

    Poppler warns on stderr about perfectly readable files, so a non-zero exit
    status with usable stdout is not a failure. The reverse is: on a malformed
    PDF ``pdftoppm`` exits **0** and writes nothing at all, so empty output is
    the error, and it is raised with poppler's own complaint attached.
    """
    out = subprocess.run([tool(name)] + list(args), capture_output=True)
    if not out.stdout:
        raise RuntimeError('%s wrote nothing: %s'
                           % (name, out.stderr.decode('utf-8', 'replace').strip()))
    return out.stdout if binary else out.stdout.decode('utf-8', 'ignore')


def text(path, layout=True, first=None, last=None):
    """Text of the PDF. Pages are separated by a form feed (``\\f``).

    ``layout=True`` keeps the columns and the indentation, which is the whole
    point for a prompter script -- the indent is how a justified line tells you
    it is a continuation, not a new paragraph.
    """
    # `-enc UTF-8` is a no-op for poppler and the difference between words and
    # punctuation for Xpdf's namesake. Always pass it.
    args = ['-enc', 'UTF-8'] + (['-layout'] if layout else [])
    if first:
        args += ['-f', str(first)]
    if last:
        args += ['-l', str(last)]
    return run('pdftotext', args + [path, '-'])


def pages(path):
    """Text, split per page. ``pdftotext`` marks the break with a form feed."""
    return text(path).split('\f')


def info(path):
    """``pdfinfo`` as a dict -- ``Pages``, ``Page size``, ``Producer``, ...."""
    out = {}
    for line in run('pdfinfo', [path]).splitlines():
        key, sep, val = line.partition(':')
        if sep:
            out[key.strip()] = val.strip()
    return out


def page_size(path):
    """``(width_pt, height_pt)`` of page 1. Letter is 612x792, A4 is 595x842."""
    size = info(path).get('Page size', '')
    nums = [float(n) for n in size.replace('x', ' ').split() if _is_num(n)]
    return (nums[0], nums[1]) if len(nums) >= 2 else (0.0, 0.0)


def _is_num(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def fonts(path):
    """``pdffonts`` as a list of dicts.

    This is how you find out what font a document you did not write actually
    uses -- a Word export names it ``ABCDEE+MalgunGothic``, the subset prefix
    being Word's, not the font's.

    Columns are split at the positions of the ``---`` rule rather than on
    whitespace: a font name can contain spaces, and so can the trailing
    ``object ID`` field.
    """
    lines = run('pdffonts', [path]).splitlines()
    head = span = None
    out = []
    for line in lines:
        if set(line.strip()) == {'-'}:
            span = [(m.start(), m.end()) for m in _rule_spans(line)]
            continue
        if span is None:
            head = line
            continue
        row = {}
        for a, b in span:
            row[head[a:b].strip()] = line[a:b].strip()
        if row.get('name'):
            out.append(row)
    return out


def _rule_spans(rule):
    return re.finditer(r'-+', rule)
