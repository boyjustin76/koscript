# -*- coding: utf-8 -*-
"""`word/document.xml` 을 **손으로** 짓는다.

왜 손으로 — `docx` (npm) 는 기존 문서를 못 열고, 파이썬 쪽 라이브러리도 남의 양식을
그대로 흉내 내기에는 거칠다. 양식을 똑같이 떠야 할 때는 OOXML 을 직접 쓰는 쪽이 빠르다.

**여기서 반드시 알아야 할 것 — `<w:pPr>` 와 `<w:rPr>` 안의 원소 차례는 스키마가 못 박는다.**
보기에는 아무 데나 넣어도 될 것 같은데, 차례가 틀리면 워드가 문서를 거부한다
(`Element 'spacing': This element is not expected`). 그래서 이 모듈이 차례를 강제한다.

  pPr : pBdr → shd → spacing → ind → jc
  rPr : rFonts → b → i → strike → color → spacing(자간) → sz → szCs → u → shd
"""

_특수 = (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'))


def 이스(s):
    for ㄱ, ㄴ in _특수:
        s = s.replace(ㄱ, ㄴ)
    return s


def 런(글, 글꼴=None, 굵게=False, 기울임=False, 취소선=False, 밑줄=False,
       색=None, 자간=None, 크기=None, 바탕색=None):
    """글 한 토막. `크기` 는 half-point (20 = 10pt)."""
    꾸 = []
    if 글꼴:
        꾸.append('<w:rFonts w:ascii="{0}" w:eastAsia="{0}" w:hAnsi="{0}" w:cs="{0}"/>'
                  .format(이스(글꼴)))
    if 굵게:
        꾸.append('<w:b/><w:bCs/>')
    if 기울임:
        꾸.append('<w:i/><w:iCs/>')
    if 취소선:
        꾸.append('<w:strike/>')
    if 색:
        꾸.append('<w:color w:val="%s"/>' % 색)
    if 자간:
        꾸.append('<w:spacing w:val="%d"/>' % 자간)
    if 크기:
        꾸.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (크기, 크기))
    if 밑줄:
        꾸.append('<w:u w:val="single"/>')
    if 바탕색:
        꾸.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % 바탕색)
    rPr = '<w:rPr>%s</w:rPr>' % ''.join(꾸) if 꾸 else ''
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rPr, 이스(글))


def 문단(런들, 앞=0, 뒤=0, 줄간=None, 테두리=None, 바탕색=None,
         들여=0, 오른들여=0, 가운데=False):
    """`런들` 은 문자열 하나거나 `런()` 결과의 목록. `줄간` 240 = 1.0줄."""
    pPr = []
    if 테두리:
        pPr.append('<w:pBdr><w:%s w:val="single" w:sz="6" w:space="6" w:color="C9D0D6"/>'
                   '</w:pBdr>' % 테두리)
    if 바탕색:
        pPr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % 바탕색)
    띄 = '<w:spacing w:before="%d" w:after="%d"%s/>' % (
        앞, 뒤, (' w:line="%d" w:lineRule="auto"' % 줄간) if 줄간 else '')
    pPr.append(띄)
    if 들여 or 오른들여:
        pPr.append('<w:ind w:left="%d" w:right="%d"/>' % (들여, 오른들여))
    if 가운데:
        pPr.append('<w:jc w:val="center"/>')
    몸 = 런들 if isinstance(런들, str) else ''.join(런들)
    return '<w:p><w:pPr>%s</w:pPr>%s</w:p>' % (''.join(pPr), 몸)


def 칸(문단들_, 너비, 바탕색=None, 테두리색='BBBBBB', 안여백=80):
    tcPr = ['<w:tcW w:w="%d" w:type="dxa"/>' % 너비]
    if 테두리색:
        tcPr.append('<w:tcBorders>%s</w:tcBorders>' % ''.join(
            '<w:%s w:val="single" w:sz="4" w:space="0" w:color="%s"/>' % (쪽, 테두리색)
            for 쪽 in ('top', 'left', 'bottom', 'right')))
    if 바탕색:
        tcPr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % 바탕색)
    tcPr.append('<w:tcMar><w:top w:w="%d" w:type="dxa"/><w:left w:w="%d" w:type="dxa"/>'
                '<w:bottom w:w="%d" w:type="dxa"/><w:right w:w="%d" w:type="dxa"/></w:tcMar>'
                % (안여백, 안여백 + 40, 안여백, 안여백 + 40))
    tcPr.append('<w:vAlign w:val="center"/>')
    몸 = 문단들_ if isinstance(문단들_, str) else ''.join(문단들_)
    return '<w:tc><w:tcPr>%s</w:tcPr>%s</w:tc>' % (''.join(tcPr), 몸)


def 줄(칸들_, 머리=False):
    trPr = '<w:trPr><w:tblHeader/></w:trPr>' if 머리 else ''
    return '<w:tr>%s%s</w:tr>' % (trPr, ''.join(칸들_))


def 표(줄들_, 너비들):
    """`tblLayout fixed` 로 둔다 — 안 그러면 워드가 열 너비를 제멋대로 다시 잡는다."""
    그리드 = ''.join('<w:gridCol w:w="%d"/>' % w for w in 너비들)
    return ('<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/>'
            '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>%s</w:tblGrid>%s</w:tbl>'
            % (sum(너비들), 그리드, ''.join(줄들_)))


# 쪽 크기 (twip). 1인치 = 1440
A4 = (11906, 16838)
LETTER = (12240, 15840)


def 구역(쪽=A4, 여백=1440, 가로=False, 머리말id=None, 위=None, 아래=None):
    w, h = (쪽[1], 쪽[0]) if 가로 else 쪽
    방향 = ' w:orient="landscape"' if 가로 else ''
    머리 = '<w:headerReference w:type="default" r:id="%s"/>' % 머리말id if 머리말id else ''
    return ('<w:sectPr>%s<w:pgSz w:w="%d" w:h="%d"%s/>'
            '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
            'w:header="700" w:footer="700" w:gutter="0"/></w:sectPr>'
            % (머리, w, h, 방향, 위 or 여백, 여백, 아래 or 여백, 여백))


_네임 = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')


def 문서(몸, 구역xml=None):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document %s><w:body>%s%s</w:body></w:document>'
            % (_네임, 몸 if isinstance(몸, str) else ''.join(몸), 구역xml or 구역()))


def 머리말달기(푼폴더, 머리말문단xml, rid='rIdHdr', 파일이름='header9.xml'):
    """쪽마다 올라가는 머리말. 관계·종류 목록까지 손봐야 워드가 인정한다.

    `구역(머리말id=rid)` 과 짝으로 쓴다.
    """
    import os
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<w:hdr %s>%s</w:hdr>' % (_네임, 머리말문단xml))
    with open(os.path.join(푼폴더, 'word', 파일이름), 'w', encoding='utf-8') as f:
        f.write(xml)

    rels = os.path.join(푼폴더, 'word', '_rels', 'document.xml.rels')
    with open(rels, encoding='utf-8') as f:
        r = f.read()
    if 파일이름 not in r:
        r = r.replace('</Relationships>',
                      '<Relationship Id="%s" Type="http://schemas.openxmlformats.org/'
                      'officeDocument/2006/relationships/header" Target="%s"/>'
                      '</Relationships>' % (rid, 파일이름))
        with open(rels, 'w', encoding='utf-8') as f:
            f.write(r)

    ct = os.path.join(푼폴더, '[Content_Types].xml')
    with open(ct, encoding='utf-8') as f:
        c = f.read()
    if 파일이름 not in c:
        c = c.replace('</Types>',
                      '<Override PartName="/word/%s" ContentType="application/'
                      'vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
                      '</Types>' % 파일이름)
        with open(ct, 'w', encoding='utf-8') as f:
            f.write(c)
    return rid
