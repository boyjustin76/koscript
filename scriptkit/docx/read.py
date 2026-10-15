# -*- coding: utf-8 -*-
"""`word/document.xml` 에서 글과 **사람이 남긴 표시**를 읽는다.

사람이 검토한 판은 보통 이렇게 온다 — 지울 것은 취소선, 고친 것은 밑줄, 살릴 것은 빨강.
그 표시는 `pandoc` 이나 글만 뽑는 도구로는 **안 보인다.** 표시가 일의 핵심인데 사라진다.
그래서 런(run)마다 꾸밈을 같이 읽는다.

주의 — 워드는 한 문장을 여러 런으로 쪼갠다(맞춤법 검사·수정 이력 때문에).
눈에 보이는 문구가 XML 에 **이어진 문자열로 없을 수 있다.**
"""
import re

_문단 = re.compile(r'<w:p\b[^>]*>.*?</w:p>|<w:p\b[^>]*/>', re.S)
_런 = re.compile(r'<w:r\b[^>]*>(.*?)</w:r>', re.S)
_꾸밈 = re.compile(r'<w:rPr>.*?</w:rPr>', re.S)
# `<w:t ...>` 만 잡는다. `[^>]*` 로 쓰면 `<w:tbl>`·`<w:tc>` 까지 걸린다 — 실제로 당했다.
_글 = re.compile(r'<w:t(?: [^>]*)?>(.*?)</w:t>', re.S)
_칸 = re.compile(r'<w:tc>.*?</w:tc>', re.S)


def 풀기(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&'))


def 문단들(본문xml):
    """문단 XML 토막의 목록. 차례가 문서 차례다."""
    return _문단.findall(본문xml)


def 글(토막):
    """문단이나 칸 토막에서 눈에 보이는 글만."""
    return 풀기(''.join(_글.findall(토막)))


def 줄들(본문xml, 빈줄빼기=True):
    """문단마다 한 줄. 표 안의 문단도 차례대로 들어간다."""
    out = [글(p) for p in 문단들(본문xml)]
    return [t for t in out if t.strip()] if 빈줄빼기 else out


def 칸들(본문xml):
    """표의 칸마다 한 덩이. 양식 문서는 칸 번호로 짚는 게 빠르다."""
    return [글(c) for c in _칸.findall(본문xml)]


def 런들(문단xml):
    """[(글, 꾸밈dict)] — 꾸밈은 굵게/기울임/취소선/밑줄/글자색/바탕색."""
    out = []
    for r in _런.findall(문단xml):
        m = _꾸밈.search(r)
        꾸 = m.group(0) if m else ''
        t = 풀기(''.join(_글.findall(r)))
        if not t:
            continue
        색 = re.search(r'<w:color w:val="([0-9A-Fa-f]{6})"', 꾸)
        칠 = re.search(r'w:fill="([0-9A-Fa-f]{6})"', 꾸)
        out.append((t, {
            '굵게': '<w:b/>' in 꾸 or '<w:b ' in 꾸,
            '기울임': '<w:i/>' in 꾸 or '<w:i ' in 꾸,
            '취소선': '<w:strike' in 꾸,
            '밑줄': '<w:u ' in 꾸 or '<w:u/>' in 꾸,
            '글자색': 색.group(1).upper() if 색 else None,
            '바탕색': 칠.group(1).upper() if 칠 else None,
        }))
    return out


def 표시읽기(본문xml, 표식=None):
    """사람이 남긴 표시를 드러내 읽는다.

    `표식` 은 {꾸밈이름: (왼쪽, 오른쪽)}. 기본은 취소선 `[-…-]` · 밑줄 `[_…_]`.
    글자색을 보려면 `{'글자색:EE0000': ('[+', '+]')}` 처럼 `꾸밈:값` 으로 준다.

    돌려주는 것 — [(문단번호, 표시가 섞인 글)]. **표시가 있는 문단만** 나온다.
    """
    표식 = 표식 or {'취소선': ('[-', '-]'), '밑줄': ('[_', '_]')}
    결과 = []
    for i, p in enumerate(문단들(본문xml)):
        조각, 있음 = [], False
        for t, 꾸 in 런들(p):
            찍 = None
            for 이름, (ㄱ, ㄴ) in 표식.items():
                키, _, 값 = 이름.partition(':')
                if (꾸.get(키) == 값) if 값 else bool(꾸.get(키)):
                    찍 = (ㄱ, ㄴ)
                    break
            if 찍:
                조각.append(찍[0] + t + 찍[1])
                있음 = True
            else:
                조각.append(t)
        if 있음:
            결과.append((i, ''.join(조각)))
    return 결과


def 표시적용(본문xml, 지울꾸밈='취소선'):
    """사람이 그어 놓은 '지울 것' 을 실제로 뺀 줄 목록. 대조할 때 쓴다."""
    out = []
    for p in 문단들(본문xml):
        글조각 = [t for t, 꾸 in 런들(p) if not 꾸.get(지울꾸밈)]
        t = ''.join(글조각).strip()
        if t:
            out.append(t)
    return out
