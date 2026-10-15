# -*- coding: utf-8 -*-
"""`.docx` 를 풀고 다시 묶는다.

`.docx` 는 XML 몇 개를 담은 zip 이다. 고치려면 풀고 → `word/document.xml` 을 고치고 → 다시 묶는다.
묶을 때 **`[Content_Types].xml` 이 맨 앞에 와야** 워드가 연다. 이름순으로 넣으면 `_rels` 가
앞서서 열리지 않는 판이 나온다 — 그래서 여기서 차례를 강제한다.

윈도우에는 `zip` 명령이 없는 경우가 많다. 그래서 `zipfile` 로만 짓는다.
"""
import os
import shutil
import zipfile

맨앞 = '[Content_Types].xml'


def 풀기(문서, 낼곳, 덮어쓰기=True):
    """`.docx` 를 폴더로 푼다. 푼 폴더 경로를 돌려준다.

    바깥에서 받은 문서라면 심볼릭 링크를 지운다 — zip 에 링크를 넣어 폴더 밖을 건드리는
    수가 있다.
    """
    if 덮어쓰기 and os.path.isdir(낼곳):
        shutil.rmtree(낼곳)
    os.makedirs(낼곳, exist_ok=True)
    with zipfile.ZipFile(문서) as z:
        z.extractall(낼곳)
    for 뿌리, _, 이름들 in os.walk(낼곳):
        for n in 이름들:
            길 = os.path.join(뿌리, n)
            if os.path.islink(길):
                os.unlink(길)
    return 낼곳


def 묶기(푼폴더, 낼파일):
    """푼 폴더를 `.docx` 로 다시 묶는다. 낸 파일 경로를 돌려준다."""
    파일들 = []
    for 뿌리, _, 이름들 in os.walk(푼폴더):
        for n in 이름들:
            길 = os.path.join(뿌리, n)
            파일들.append((os.path.relpath(길, 푼폴더).replace('\\', '/'), 길))
    if not any(안 == 맨앞 for 안, _ in 파일들):
        raise ValueError('%s 가 없다 — .docx 를 푼 폴더가 맞나?' % 맨앞)
    파일들.sort(key=lambda x: (x[0] != 맨앞, x[0]))

    if os.path.exists(낼파일):
        os.remove(낼파일)
    with zipfile.ZipFile(낼파일, 'w', zipfile.ZIP_DEFLATED) as z:
        for 안이름, 길 in 파일들:
            z.write(길, 안이름)
    return 낼파일


def 본문(푼폴더):
    """`word/document.xml` 의 경로."""
    return os.path.join(푼폴더, 'word', 'document.xml')


def 본문읽기(푼폴더):
    with open(본문(푼폴더), encoding='utf-8') as f:
        return f.read()


def 본문쓰기(푼폴더, 글):
    with open(본문(푼폴더), 'w', encoding='utf-8') as f:
        f.write(글)
