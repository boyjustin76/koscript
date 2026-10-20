# -*- coding: utf-8 -*-
"""Turn a ``.docx`` into a PDF and page images, so you can **look at what you built**.

Checking only the extracted text will catch you out. Three things it has let
through: a literal ``**`` where Markdown emphasis was meant, a table broken across
a page, and a highlight colour landing on the wrong line. None of them show up in
the text; all of them are obvious in a picture. After the third time this step
became a rule.

On Windows:

- the usual way to drive LibreOffice from Python uses ``socket.AF_UNIX`` and dies
- calling ``soffice.exe`` from Git Bash **returns quietly and writes no PDF**
- poppler is often installed but not on ``PATH``

So the executables are located explicitly, and on Windows LibreOffice is launched
through PowerShell's ``Start-Process -Wait``, which actually waits.
"""
import glob
import os
import shutil
import subprocess
import sys

from ..pdfform import poppler as _poppler

_WINDOWS = sys.platform.startswith('win')

_SOFFICE_CANDIDATES = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    '/usr/bin/soffice', '/usr/local/bin/soffice',
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
]


def find_soffice(explicit=None):
    """Path to LibreOffice. ``SOFFICE`` overrides the search."""
    for p in filter(None, [explicit, os.environ.get('SOFFICE')]):
        if os.path.exists(p):
            return p
    found = shutil.which('soffice') or shutil.which('libreoffice')
    if found:
        return found
    for p in _SOFFICE_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError('soffice not found. Install LibreOffice, or point SOFFICE at it.')


def find_poppler(name, explicit=None):
    """Path to one poppler binary -- see :mod:`koscript.pdfform.poppler`.

    ``explicit`` may be the binary or the folder holding it; otherwise
    ``KOSCRIPT_POPPLER`` (or the older ``POPPLER_BIN``) and the usual install
    locations are searched.
    """
    if explicit:
        here = os.path.join(explicit, name + ('.exe' if _WINDOWS else '')) \
            if os.path.isdir(explicit) else explicit
        if os.path.exists(here):
            return here
    return _poppler.tool(name)


def to_pdf(docx_path, out_dir=None, soffice=None, timeout=180):
    """``.docx`` -> ``.pdf``. Returns the path of the PDF it made."""
    docx_path = os.path.abspath(docx_path)
    out_dir = os.path.abspath(out_dir or os.path.dirname(docx_path))
    exe = find_soffice(soffice)
    args = ['--headless', '--norestore', '--convert-to', 'pdf', '--outdir', out_dir, docx_path]
    if _WINDOWS:
        # Only `Start-Process -Wait` waits for it. Called directly it returns at once.
        quote = lambda s: '"%s"' % s.replace('"', '`"')      # noqa: E731
        ps = ('Start-Process -FilePath %s -ArgumentList %s -Wait -NoNewWindow'
              % (quote(exe), ','.join(quote(a) for a in args)))
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                       check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run([exe] + args, check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    made = os.path.join(out_dir, os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
    if not os.path.exists(made):
        raise RuntimeError('no PDF came out: %s' % made)
    return made


def page_images(pdf, prefix, dpi=100, first=None, last=None, fmt='jpeg', poppler=None):
    """PDF -> one image per page. Returns the paths it wrote.

    ``pdftoppm`` zero-pads the page number to the width of the page **count**
    (``-01.jpg`` ... ``-12.jpg``), so do not build the names yourself.
    """
    exe = find_poppler('pdftoppm', poppler)
    args = [exe, '-' + fmt, '-r', str(dpi)]
    if first:
        args += ['-f', str(first)]
    if last:
        args += ['-l', str(last)]
    subprocess.run(args + [pdf, prefix], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ext = 'jpg' if fmt == 'jpeg' else fmt
    return sorted(glob.glob('%s-*.%s' % (prefix, ext)))


def preview(docx_path, out_dir, dpi=100, **kw):
    """One ``.docx`` to a PDF and page images. Returns ``(pdf, [images])``."""
    pdf = to_pdf(docx_path, out_dir, soffice=kw.get('soffice'))
    head = os.path.join(out_dir, os.path.splitext(os.path.basename(docx_path))[0])
    return pdf, page_images(pdf, head, dpi=dpi, poppler=kw.get('poppler'))
