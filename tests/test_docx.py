# -*- coding: utf-8 -*-
"""docx 묶음 시험 — 표본 문서를 **코드로 지어** 쓴다. 회사 파일이 없어도 돌아가야 한다."""
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scriptkit.docx import build, diff, edit, pack, read   # noqa: E402

_CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       '<Default Extension="xml" ContentType="application/xml"/>'
       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
       'relationships+xml"/>'
       '<Override PartName="/word/document.xml" ContentType="application/vnd.'
       'openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
         '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
_DOCRELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"/>')


def 표본docx(길, 본문xml):
    os.makedirs(os.path.dirname(길), exist_ok=True)
    with zipfile.ZipFile(길, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', _CT)
        z.writestr('_rels/.rels', _RELS)
        z.writestr('word/document.xml', 본문xml)
        z.writestr('word/_rels/document.xml.rels', _DOCRELS)
    return 길


@pytest.fixture
def 본문():
    몸 = [
        build.문단(build.런('첫 줄입니다.')),
        build.문단([build.런('그래서 다음에는 그대로 '),
                    build.런('무너지는 날도 있죠.', 취소선=True),
                    build.런('무너지죠.', 밑줄=True)]),
        build.문단(build.런('표 & 꺾쇠 <여기> 도 섞인다.')),
        build.표([build.줄([build.칸(build.문단(build.런('칸1')), 2000),
                           build.칸(build.문단(build.런('칸2')), 4000)])],
                 [2000, 4000]),
    ]
    return build.문서(몸)


def test_묶을때_콘텐츠타입이_맨앞(tmp_path, 본문):
    푼곳 = str(tmp_path / '푼것')
    표본docx(str(tmp_path / '표본.docx'), 본문)
    pack.풀기(str(tmp_path / '표본.docx'), 푼곳)
    낸것 = pack.묶기(푼곳, str(tmp_path / '다시.docx'))
    with zipfile.ZipFile(낸것) as z:
        assert z.namelist()[0] == '[Content_Types].xml'


def test_풀고_묶으면_본문이_그대로(tmp_path, 본문):
    표본docx(str(tmp_path / '표본.docx'), 본문)
    푼곳 = pack.풀기(str(tmp_path / '표본.docx'), str(tmp_path / '푼것'))
    assert pack.본문읽기(푼곳) == 본문
    pack.묶기(푼곳, str(tmp_path / '다시.docx'))
    다시 = pack.풀기(str(tmp_path / '다시.docx'), str(tmp_path / '푼것2'))
    assert pack.본문읽기(다시) == 본문


def test_줄읽기와_엔티티풀기(본문):
    줄 = read.줄들(본문)
    assert 줄[0] == '첫 줄입니다.'
    assert '표 & 꺾쇠 <여기> 도 섞인다.' in 줄          # &amp; · &lt; 가 풀려야 한다


def test_표칸읽기(본문):
    assert read.칸들(본문) == ['칸1', '칸2']


def test_표토막이_본문으로_새지_않는다(본문):
    """`<w:t[^>]*>` 로 잡으면 `<w:tbl>` 이 걸려 XML 이 글로 섞여 나온다."""
    for 줄 in read.줄들(본문):
        assert '<w:' not in 줄


def test_표시읽기(본문):
    표시 = read.표시읽기(본문)
    assert len(표시) == 1
    _, 글 = 표시[0]
    assert 글 == '그래서 다음에는 그대로 [-무너지는 날도 있죠.-][_무너지죠._]'


def test_표시적용하면_취소선이_빠진다(본문):
    줄 = read.표시적용(본문)
    assert '그래서 다음에는 그대로 무너지죠.' in 줄
    assert not any('무너지는 날도' in l for l in 줄)


def test_한번만_센다(본문):
    바뀐 = edit.한번만(본문, '첫 줄입니다.', '고친 줄입니다.')
    assert '고친 줄입니다.' in read.줄들(바뀐)
    with pytest.raises(ValueError):
        edit.한번만(본문, '없는 말', 'x')
    with pytest.raises(ValueError):           # 두 번 나오는 말은 막는다
        edit.한번만(본문 + 본문, '첫 줄입니다.', 'x')


def test_여러번은_하나라도_틀리면_아무것도_안바꾼다(본문):
    with pytest.raises(ValueError):
        edit.여러번(본문, [('첫 줄입니다.', 'A'), ('없는 말', 'B')])


def test_문단바꾸기와_머리따기(본문):
    옛 = read.문단들(본문)[0]
    새 = edit.머리따기(옛) + build.런('갈아 끼운 줄') + '</w:p>'
    바뀐 = edit.문단바꾸기(본문, 0, 새)
    assert read.줄들(바뀐)[0] == '갈아 끼운 줄'


def test_지킴(본문):
    assert edit.지킴(본문, 없어야=['없는 말'], 있어야=['첫 줄입니다.'])
    with pytest.raises(ValueError):
        edit.지킴(본문, 없어야=['첫 줄입니다.'])


def test_대조는_조용히_바뀐_곳도_잡는다(본문):
    딴판 = 본문.replace('첫 줄입니다.', '몰래 바꾼 줄입니다.')
    지움, 넣음 = diff.바뀐줄(본문, 딴판)
    assert 지움 == ['첫 줄입니다.']
    assert 넣음 == ['몰래 바꾼 줄입니다.']


def test_pPr_rPr_원소차례가_스키마대로(본문):
    """차례가 틀리면 워드가 문서를 거부한다 — 실제로 당했다."""
    p = build.문단(build.런('x', 글꼴='맑은 고딕', 굵게=True, 색='FF0000',
                            자간=20, 크기=20, 바탕색='FFFF00'),
                   테두리='bottom', 바탕색='EEEEEE', 들여=100, 줄간=360, 가운데=True)
    rPr = p[p.index('<w:rPr>'):p.index('</w:rPr>')]
    assert (rPr.index('rFonts') < rPr.index('<w:b/>') < rPr.index('w:color')
            < rPr.index('<w:spacing') < rPr.index('<w:sz ') < rPr.index('<w:shd'))
    pPr = p[p.index('<w:pPr>'):p.index('</w:pPr>')]
    assert (pPr.index('pBdr') < pPr.index('<w:shd') < pPr.index('<w:spacing')
            < pPr.index('<w:ind') < pPr.index('<w:jc'))


def test_묶기는_docx가_아닌_폴더를_거부한다(tmp_path):
    (tmp_path / '아무것').mkdir()
    (tmp_path / '아무것' / 'a.txt').write_text('x', encoding='utf-8')
    with pytest.raises(ValueError):
        pack.묶기(str(tmp_path / '아무것'), str(tmp_path / 'x.docx'))
