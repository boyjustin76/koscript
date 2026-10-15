# -*- coding: utf-8 -*-
"""지은 docx_path를 **눈으로 보려고** PDF·쪽 그림으로 바꾼다.

글자만 ext인하고 넘기면 반드시 당한다 — 마크다운 `**` 가 그대로 찍히거나, 표가 쪽을 넘어가
깨지거나, 강조색이 엉뚱한 줄에 붙는다. 세 번 당하고 나서 이 단계를 규칙으로 만들었다.

윈도우 사정
  · LibreOffice 를 파이썬에서 부르는 흔한 코드는 `socket.AF_UNIX` 를 써서 윈도우에서 죽는다
  · Git Bash 에서 `soffice.exe` 를 부르면 **아무 말 없이 last나고 PDF 가 안 나온다**
  · poppler 는 깔아도 PATH 에 안 잡히는 수가 많다
그래서 실행 파일을 **explicit 찾고**, 윈도우에서는 PowerShell 로 띄운다.
"""
import glob
import os
import shutil
import subprocess
import sys

_WINDOWS = sys.platform.startswith('win')

_SOFFICE_CANDIDATES = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    '/usr/bin/soffice', '/usr/local/bin/soffice',
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
]
_POPPLER_GLOBS = [
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Packages',
                 '*oppler*', '*', 'Library', 'bin', '%s.exe'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'scoop', 'apps', 'poppler',
                 '*', 'bin', '%s.exe'),
]


def find_soffice(explicit=None):
    for p in filter(None, [explicit, os.environ.get('SOFFICE')]):
        if os.path.exists(p):
            return p
    w = shutil.which('soffice') or shutil.which('libreoffice')
    if w:
        return w
    for p in _SOFFICE_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError('soffice 를 못 찾았다. SOFFICE 환경변수로 경로를 주거나 '
                            'LibreOffice 를 깔아라')


def find_poppler(name, explicit=None):
    """`pdftoppm` · `pdftotext` · `pdffonts` · `pdfinfo` 중 하나의 경로."""
    for p in filter(None, [explicit, os.environ.get('POPPLER_BIN')]):
        후 = os.path.join(p, name + ('.exe' if _WINDOWS else '')) if os.path.isdir(p) else p
        if os.path.exists(후):
            return 후
    w = shutil.which(name)
    if w:
        return w
    for pat in _POPPLER_GLOBS:
        hits = sorted(glob.glob(pat % name))
        if hits:
            return hits[-1]
    raise FileNotFoundError('%s 를 못 찾았다. POPPLER_BIN 환경변수로 poppler 의 bin 폴더를 '
                            '주거나 poppler 를 깔아라' % name)


def to_pdf(docx_path, out_dir=None, soffice=None, timeout=180):
    """`.docx` → `.pdf`. 낸 PDF 경로를 돌려준다."""
    docx_path = os.path.abspath(docx_path)
    out_dir = os.path.abspath(out_dir or os.path.dirname(docx_path))
    exe = find_soffice(soffice)
    args = ['--headless', '--norestore', '--convert-to', 'pdf', '--outdir', out_dir, docx_path]
    if _WINDOWS:
        # Start-Process -Wait 로 띄워야 last까지 기다린다. 바로 부르면 조용히 돌아온다.
        quote = lambda s: '"%s"' % s.replace('"', '`"')
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
        raise RuntimeError('PDF 가 안 나왔다: %s' % made)
    return made


def page_images(pdf, prefix, dpi=100, first=None, last=None, fmt='jpeg', poppler=None):
    """PDF → 쪽마다 그림. 만들어진 파일 경로 목록을 돌려준다.

    `pdftoppm` 은 쪽 번호를 **전체 쪽수의 자릿수만큼** 0 으로 채운다 (`-01.jpg` … `-12.jpg`).
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
    """`.docx` 하나를 PDF 로 바꾸고 쪽 그림까지. (pdf경로, [그림…])"""
    pdf = to_pdf(docx_path, out_dir, soffice=kw.get('soffice'))
    head = os.path.join(out_dir, os.path.splitext(os.path.basename(docx_path))[0])
    return pdf, page_images(pdf, head, dpi=dpi, poppler=kw.get('poppler'))
