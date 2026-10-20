# -*- coding: utf-8 -*-
"""Read a ``.prproj`` without opening Premiere.

A ``.prproj`` is **gzipped XML**. You can read the whole project -- sequences,
effects, keyframes, media paths -- with nothing but ``gzip``. Checking what a project
references by taking screenshots of Premiere is wasted effort.

Media paths live in three tags::

    <ActualMediaFilePath>   absolute -- what Premiere actually opens
    <FilePath>              absolute
    <RelativePath>          relative to the project file -- the fallback

**``RelativePath`` is escaped twice** (``&`` arrives as ``&amp;amp;``). That is
Premiere's own habit, not corruption: untouched projects show it too, with
``ActualMediaFilePath`` normal. Unescape it once and you will report healthy clips
as broken.

The point of ``referencing`` is to run it **before you move a folder**. Moving one
once took ten sources offline in an edit nobody thought was related: the person
moving checked that every file was in the box, and never asked *who points at this
path*. Check the using side, not the packing side.
"""
import glob
import gzip
import html
import os
import re

ABS_TAGS = ('ActualMediaFilePath', 'FilePath')
REL_TAG = 'RelativePath'
AUTOSAVE_MARK = 'Auto-Save'


def read_xml(project):
    """The project's XML. Handles uncompressed projects too."""
    try:
        with gzip.open(project, 'rb') as f:
            return f.read().decode('utf-8', 'replace')
    except OSError:
        with open(project, 'rb') as f:
            return f.read().decode('utf-8', 'replace')


def tag_values(xml, tag):
    """Every ``<tag>...</tag>`` body. Plain scanning -- the files are big and flat."""
    out, k = [], 0
    open_t, close_t = '<%s>' % tag, '</%s>' % tag
    while True:
        a = xml.find(open_t, k)
        if a < 0:
            return out
        b = xml.find(close_t, a)
        if b < 0:
            return out
        out.append(xml[a + len(open_t):b].strip())
        k = b + len(close_t)


def is_absolute(s):
    return len(s) > 3 and s[1] == ':' and s[0].isalpha() and s[2] in ('\\', '/')


def file_name(path):
    """Last component of a path, whichever separator **the writing machine** used.

    The paths inside a ``.prproj`` belong to the machine that saved it, and that
    is almost always Windows. ``os.path.basename`` on Linux or macOS does not
    split a backslash, so ``Z:\\gone\\b.mp4`` came back whole, the name never
    matched its relative-path candidate, and a clip Premiere would open fine was
    reported offline. Read the file's separators, not the host's.
    """
    return re.split(r'[\\/]', path)[-1]


def links(project, xml=None):
    """``(absolute paths, file names reachable by relative path)``."""
    xml = read_xml(project) if xml is None else xml
    base = os.path.dirname(os.path.abspath(project))
    absolute, relative = set(), set()
    for tag in ABS_TAGS:
        for v in tag_values(xml, tag):
            v = html.unescape(v)
            if is_absolute(v):
                absolute.add(v)
    for v in tag_values(xml, REL_TAG):
        v = html.unescape(html.unescape(v))       # 두 번 — 한 번만 풀면 멀쩡한 클립이 끊긴 걸로 읽힌다
        if not v:
            continue
        p = os.path.normpath(os.path.join(base, v.replace('\\', os.sep)))
        if os.path.exists(p):
            relative.add(file_name(p).lower())
    return absolute, relative


def offline(project, xml=None):
    """``(missing paths, total referenced)``.

    Counted missing only when the absolute path is gone **and** no relative-path
    candidate of the same name exists -- otherwise Premiere would still find it.
    """
    absolute, relative = links(project, xml)
    gone = sorted(p for p in absolute
                  if not os.path.exists(p) and file_name(p).lower() not in relative)
    return gone, len(absolute)


def projects(root, include_autosave=False):
    """Every ``.prproj`` under ``root``. Auto-save copies are skipped by default."""
    for p in sorted(glob.glob(os.path.join(root, '**', '*.prproj'), recursive=True)):
        if include_autosave or AUTOSAVE_MARK not in p:
            yield p


def referencing(needle, root, include_autosave=False):
    """Which projects under ``root`` point at a path containing ``needle``.

    **Run this before moving or deleting a folder.** Include the destination folder in
    ``root`` as well -- a project already sitting there may still point at the old path.
    """
    needle = needle.lower()
    hits = []
    for p in projects(root, include_autosave):
        try:
            absolute, _ = links(p)
        except Exception:
            continue
        matched = sorted(a for a in absolute if needle in a.lower())
        if matched:
            hits.append((p, matched))
    return hits
