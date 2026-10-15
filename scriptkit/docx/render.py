# -*- coding: utf-8 -*-
"""지은 문서를 **눈으로 보려고** PDF·쪽 그림으로 바꾼다.

글자만 확인하고 넘기면 반드시 당한다 — 마크다운 `**` 가 그대로 찍히거나, 표가 쪽을 넘어가
깨지거나, 강조색이 엉뚱한 줄에 붙는다. 세 번 당하고 나서 이 단계를 규칙으로 만들었다.

윈도우 사정
  · LibreOffice 를 파이썬에서 부르는 흔한 코드는 `socket.AF_UNIX` 를 써서 윈도우에서 죽는다
  · Git Bash 에서 `soffice.exe` 를 부르면 **아무 말 없이 끝나고 PDF 가 안 나온다**
  · poppler 는 깔아도 PATH 에 안 잡히는 수가 많다
그래서 실행 파일을 **직접 찾고**, 윈도우에서는 PowerShell 로 띄운다.
"""
import glob
import os
import shutil
import subprocess
import sys

_윈도우 = sys.platform.startswith('win')

_SOFFICE_후보 = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    '/usr/bin/soffice', '/usr/local/bin/soffice',
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
]
_POPPLER_글롭 = [
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Packages',
                 '*oppler*', '*', 'Library', 'bin', '%s.exe'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'scoop', 'apps', 'poppler',
                 '*', 'bin', '%s.exe'),
]


def 찾기_soffice(직접=None):
    for p in filter(None, [직접, os.environ.get('SOFFICE')]):
        if os.path.exists(p):
            return p
    w = shutil.which('soffice') or shutil.which('libreoffice')
    if w:
        return w
    for p in _SOFFICE_후보:
        if os.path.exists(p):
            return p
    raise FileNotFoundError('soffice 를 못 찾았다. SOFFICE 환경변수로 경로를 주거나 '
                            'LibreOffice 를 깔아라')


def 찾기_poppler(이름, 직접=None):
    """`pdftoppm` · `pdftotext` · `pdffonts` · `pdfinfo` 중 하나의 경로."""
    for p in filter(None, [직접, os.environ.get('POPPLER_BIN')]):
        후 = os.path.join(p, 이름 + ('.exe' if _윈도우 else '')) if os.path.isdir(p) else p
        if os.path.exists(후):
            return 후
    w = shutil.which(이름)
    if w:
        return w
    for 패 in _POPPLER_글롭:
        칸 = sorted(glob.glob(패 % 이름))
        if 칸:
            return 칸[-1]
    raise FileNotFoundError('%s 를 못 찾았다. POPPLER_BIN 환경변수로 poppler 의 bin 폴더를 '
                            '주거나 poppler 를 깔아라' % 이름)


def pdf로(문서, 낼폴더=None, soffice=None, 시간=180):
    """`.docx` → `.pdf`. 낸 PDF 경로를 돌려준다."""
    문서 = os.path.abspath(문서)
    낼폴더 = os.path.abspath(낼폴더 or os.path.dirname(문서))
    exe = 찾기_soffice(soffice)
    인자 = ['--headless', '--norestore', '--convert-to', 'pdf', '--outdir', 낼폴더, 문서]
    if _윈도우:
        # Start-Process -Wait 로 띄워야 끝까지 기다린다. 바로 부르면 조용히 돌아온다.
        따옴 = lambda s: '"%s"' % s.replace('"', '`"')
        ps = ('Start-Process -FilePath %s -ArgumentList %s -Wait -NoNewWindow'
              % (따옴(exe), ','.join(따옴(a) for a in 인자)))
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                       check=True, timeout=시간,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run([exe] + 인자, check=True, timeout=시간,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    낸것 = os.path.join(낼폴더, os.path.splitext(os.path.basename(문서))[0] + '.pdf')
    if not os.path.exists(낸것):
        raise RuntimeError('PDF 가 안 나왔다: %s' % 낸것)
    return 낸것


def 쪽그림(pdf, 머리말, dpi=100, 처음=None, 끝=None, 꼴='jpeg', poppler=None):
    """PDF → 쪽마다 그림. 만들어진 파일 경로 목록을 돌려준다.

    `pdftoppm` 은 쪽 번호를 **전체 쪽수의 자릿수만큼** 0 으로 채운다 (`-01.jpg` … `-12.jpg`).
    """
    exe = 찾기_poppler('pdftoppm', poppler)
    인자 = [exe, '-' + 꼴, '-r', str(dpi)]
    if 처음:
        인자 += ['-f', str(처음)]
    if 끝:
        인자 += ['-l', str(끝)]
    subprocess.run(인자 + [pdf, 머리말], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    확 = 'jpg' if 꼴 == 'jpeg' else 꼴
    return sorted(glob.glob('%s-*.%s' % (머리말, 확)))


def 보기(문서, 낼폴더, dpi=100, **kw):
    """`.docx` 하나를 PDF 로 바꾸고 쪽 그림까지. (pdf경로, [그림…])"""
    pdf = pdf로(문서, 낼폴더, soffice=kw.get('soffice'))
    머리 = os.path.join(낼폴더, os.path.splitext(os.path.basename(문서))[0])
    return pdf, 쪽그림(pdf, 머리, dpi=dpi, poppler=kw.get('poppler'))
