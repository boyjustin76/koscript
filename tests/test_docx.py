# -*- coding: utf-8 -*-
"""docx tests. The sample document is **built in code** so the suite runs anywhere."""
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from koscript.docx import build, diff, edit, pack, read   # noqa: E402

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


def make_docx(path, body_xml):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', _CT)
        z.writestr('_rels/.rels', _RELS)
        z.writestr('word/document.xml', body_xml)
        z.writestr('word/_rels/document.xml.rels', _DOCRELS)
    return path


@pytest.fixture
def body():
    parts = [
        build.para(build.run('첫 줄입니다.')),
        build.para([build.run('그래서 다음에는 그대로 '),
                    build.run('무너지는 날도 있죠.', strike=True),
                    build.run('무너지죠.', underline=True)]),
        build.para(build.run('표 & 꺾쇠 <여기> 도 섞인다.')),
        build.table([build.row([build.cell(build.para(build.run('칸1')), 2000),
                                build.cell(build.para(build.run('칸2')), 4000)])],
                    [2000, 4000]),
    ]
    return build.document(parts)


def test_content_types_is_first_entry(tmp_path, body):
    make_docx(str(tmp_path / 'sample.docx'), body)
    src = pack.unpack(str(tmp_path / 'sample.docx'), str(tmp_path / 'src'))
    out = pack.repack(src, str(tmp_path / 'again.docx'))
    with zipfile.ZipFile(out) as z:
        assert z.namelist()[0] == '[Content_Types].xml'


def test_round_trip_keeps_body_byte_for_byte(tmp_path, body):
    make_docx(str(tmp_path / 'sample.docx'), body)
    src = pack.unpack(str(tmp_path / 'sample.docx'), str(tmp_path / 'src'))
    assert pack.read_body(src) == body
    pack.repack(src, str(tmp_path / 'again.docx'))
    again = pack.unpack(str(tmp_path / 'again.docx'), str(tmp_path / 'src2'))
    assert pack.read_body(again) == body


def test_lines_and_entity_unescaping(body):
    out = read.lines(body)
    assert out[0] == '첫 줄입니다.'
    assert '표 & 꺾쇠 <여기> 도 섞인다.' in out      # &amp; and &lt; must come back


def test_table_cells(body):
    assert read.cells(body) == ['칸1', '칸2']


def test_table_markup_does_not_leak_into_text(body):
    """`<w:t[^>]*>` also matches `<w:tbl>`; raw XML then shows up as text."""
    for line in read.lines(body):
        assert '<w:' not in line


def test_read_marks(body):
    marked = read.read_marks(body)
    assert len(marked) == 1
    _, text = marked[0]
    assert text == '그래서 다음에는 그대로 [-무너지는 날도 있죠.-][_무너지죠._]'


def test_lines_after_marks_drops_struck_text(body):
    out = read.lines_after_marks(body)
    assert '그래서 다음에는 그대로 무너지죠.' in out
    assert not any('무너지는 날도' in l for l in out)


def test_replace_once_counts(body):
    out = edit.replace_once(body, '첫 줄입니다.', '고친 줄입니다.')
    assert '고친 줄입니다.' in read.lines(out)
    with pytest.raises(ValueError):
        edit.replace_once(body, '없는 말', 'x')
    with pytest.raises(ValueError):
        edit.replace_once(body + body, '첫 줄입니다.', 'x')


def test_replace_all_once_is_all_or_nothing(body):
    with pytest.raises(ValueError):
        edit.replace_all_once(body, [('첫 줄입니다.', 'A'), ('없는 말', 'B')])


def test_replace_paragraph_and_head(body):
    old = read.paragraphs(body)[0]
    new = edit.paragraph_head(old) + build.run('갈아 끼운 줄') + '</w:p>'
    out = edit.replace_paragraph(body, 0, new)
    assert read.lines(out)[0] == '갈아 끼운 줄'


def test_assert_text(body):
    assert edit.assert_text(body, absent=['없는 말'], present=['첫 줄입니다.'])
    with pytest.raises(ValueError):
        edit.assert_text(body, absent=['첫 줄입니다.'])


def test_diff_catches_unmarked_changes(body):
    other = body.replace('첫 줄입니다.', '몰래 바꾼 줄입니다.')
    removed, added = diff.changed_lines(body, other)
    assert removed == ['첫 줄입니다.']
    assert added == ['몰래 바꾼 줄입니다.']


def test_schema_child_order(body):
    """Word rejects the file if these are out of order. It has happened."""
    p = build.para(build.run('x', font='맑은 고딕', bold=True, color='FF0000',
                             spacing=20, size=20, fill='FFFF00'),
                   border='bottom', fill='EEEEEE', indent=100, line=360, center=True)
    rpr = p[p.index('<w:rPr>'):p.index('</w:rPr>')]
    assert (rpr.index('rFonts') < rpr.index('<w:b/>') < rpr.index('w:color')
            < rpr.index('<w:spacing') < rpr.index('<w:sz ') < rpr.index('<w:shd'))
    ppr = p[p.index('<w:pPr>'):p.index('</w:pPr>')]
    assert (ppr.index('pBdr') < ppr.index('<w:shd') < ppr.index('<w:spacing')
            < ppr.index('<w:ind') < ppr.index('<w:jc'))


def test_repack_rejects_a_folder_that_is_not_a_docx(tmp_path):
    (tmp_path / 'plain').mkdir()
    (tmp_path / 'plain' / 'a.txt').write_text('x', encoding='utf-8')
    with pytest.raises(ValueError):
        pack.repack(str(tmp_path / 'plain'), str(tmp_path / 'x.docx'))
