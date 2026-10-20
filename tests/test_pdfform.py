# -*- coding: utf-8 -*-
"""pdfform tests. The prompter ones need no poppler -- they run on extracted text,
which is also how you reproduce a wrong subtitle without shipping the PDF."""
import io
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from koscript.pdfform import poppler, probe, prompter   # noqa: E402

HEAD = '보기 스크립트 | 1부'

# A prompter script as `pdftotext -layout` hands it over: one spoken line per
# paragraph, a blank line between them, the running header carrying the form feed.
PAGE1 = [
    HEAD,
    '',
    'S1 · SHOOTING SCRIPT',
    '',
    '표지에 적힌 말은 읽지 않습니다.',
    '',
    'INTRO. 첫 구간의 제목',
    '',
    '안녕하세요.',
    '',
    "오늘은 밴드를 두 개 겹쳐 쓰는 '더블",          # trap 1: one blank is a line wrap
    '',
    "볼린저 밴드' 방식을 봅니다.",
    '',
    '기간 20 과 표준편차 2 를 같이 봅니다.',          # trap 6: number split from particle
    '',
    '[화면 진행 · 읽지 않음]',                        # trap: a block not to be read
    '',
    '여기는 읽지 않는 설명 블록입니다.',
    '',
    '',
    '1. 둘째 구간',
    '',
    '여기까지가 기본입니다',                          # trap 5: no final period
    '',
    '이제 적용해 봅니다. (화면을 보며 설명)',          # trap 4: direction inside the line
    '',
    '',
    '• 첫째 항목입니다.',
    '   이어지는 줄입니다.',
    '• 둘째 항목입니다.',
    '',
    '',
    '이 자리는 절대',                                 # trap 3: justified wrap inside a word
    '   적인 기준이 됩니다.',
    '',
    '',
    '문장이 쪽을 넘어가도',                           # trap 2: the page turns here
]
PAGE2 = [
    '',
    '',
    '',
    '',
    '한 문장으로 이어져야 합니다.',
    '',
    'OUTRO',
    '',
    '여기까지입니다.',
]
TEXT = '\n'.join(PAGE1 + ['\f' + HEAD] + PAGE2)


def parsed(spoken=None):
    return prompter.parse(TEXT, spoken=spoken)


def sentences(sections, name):
    return [s['sentences'] for s in sections if s['section'] == name][0]


# ── the running header, found rather than configured ───────────────────────
def test_the_running_header_is_detected_without_being_named():
    assert HEAD in prompter.page_furniture(TEXT)


def test_a_repeated_sentence_in_mid_page_is_not_mistaken_for_a_header():
    """Position is half the test -- furniture sits at the rim of every page."""
    page = '머리말\n\n첫 줄입니다.\n\n둘째 줄입니다.\n\n같은 말을 두 번 합니다.\n\n넷째 줄입니다.\n\n다섯째 줄입니다.\n\n꼬리말'
    body = page + '\f' + page
    got = prompter.page_furniture(body)
    assert '머리말' in got and '꼬리말' in got
    assert '같은 말을 두 번 합니다.' not in got


def test_the_header_is_not_read_aloud():
    said = ' '.join(t for s in parsed()[0] for t in s['sentences'])
    assert HEAD not in said


# ── sections ───────────────────────────────────────────────────────────────
def test_sections_are_found_in_order():
    assert [s['section'] for s in parsed()[0]] == ['INTRO', '1', 'OUTRO']


def test_the_section_title_is_kept_apart_from_the_spoken_lines():
    intro = parsed()[0][0]
    assert intro['title'] == '첫 구간의 제목'
    assert '첫 구간의 제목' not in ' '.join(intro['sentences'])


def test_a_cover_page_has_nowhere_to_go_and_is_dropped():
    said = ' '.join(t for s in parsed()[0] for t in s['sentences'])
    assert '표지에 적힌' not in said and 'SHOOTING' not in said


# ── trap 1: one blank line is a line wrap, not a paragraph break ───────────
def test_a_single_blank_line_does_not_cut_a_sentence_in_half():
    got = sentences(parsed()[0], 'INTRO')
    assert "오늘은 밴드를 두 개 겹쳐 쓰는 '더블 볼린저 밴드' 방식을 봅니다." in got
    assert not any(t.endswith("'더블") for t in got)


def test_two_blank_lines_do_separate_paragraphs():
    got = sentences(parsed()[0], '1')
    assert '여기까지가 기본입니다' in got


# ── trap 2: a page turn is not a paragraph break ───────────────────────────
def test_a_sentence_survives_the_page_turn():
    assert '문장이 쪽을 넘어가도 한 문장으로 이어져야 합니다.' in sentences(parsed()[0], '1')


def test_a_page_turn_without_a_running_header_also_holds_the_sentence():
    """The form feed is enough. A script with no header still must not be cut."""
    body = 'INTRO. 제목\n\n앞쪽에서 시작한 문장이\f\n\n\n\n뒤쪽에서 끝납니다.'
    got, _ = prompter.parse(body)
    assert got[0]['sentences'] == ['앞쪽에서 시작한 문장이 뒤쪽에서 끝납니다.']


# ── trap 3: a justified wrap lands inside a word ───────────────────────────
def test_an_undecidable_wrap_is_reported_not_guessed():
    _, unresolved = parsed()
    assert ('절대', '적인') in unresolved


def test_a_transcript_decides_the_wrap():
    got, unresolved = parsed(spoken='이 자리는 절대적인 기준이 됩니다')
    assert '이 자리는 절대적인 기준이 됩니다.' in sentences(got, '1')
    assert ('절대', '적인') not in unresolved


def test_a_transcript_can_also_decide_to_keep_the_space():
    got, _ = parsed(spoken='이 자리는 절대 적인 기준이 됩니다')
    assert '이 자리는 절대 적인 기준이 됩니다.' in sentences(got, '1')


def test_punctuation_before_the_wrap_settles_it_without_a_transcript():
    assert prompter.joins('첫째 항목입니다.', '이어지는 줄입니다.') is False


def test_a_wrap_before_a_bullet_is_never_a_word_split():
    got = sentences(parsed()[0], '1')
    assert '첫째 항목입니다.' in got and '둘째 항목입니다.' in got


def test_the_bullet_glyph_is_not_read_aloud():
    assert not any(t.startswith(('•', '·')) for s in parsed()[0] for t in s['sentences'])


# ── trap 4: a direction hides inside a spoken line ─────────────────────────
def test_a_parenthetical_direction_is_stripped_from_a_spoken_line():
    got = sentences(parsed()[0], '1')
    assert '이제 적용해 봅니다.' in got
    assert not any('화면을 보며' in t for t in got)


def test_a_parenthetical_that_is_read_aloud_is_kept():
    """`(가짜 신호)` is part of the sentence; the verb is what marks a direction."""
    got, _ = prompter.parse('INTRO. 제목\n\n잦은 휩소(가짜 신호)를 걸러냅니다.')
    assert got[0]['sentences'] == ['잦은 휩소(가짜 신호)를 걸러냅니다.']


def test_a_bracketed_block_is_not_read_aloud():
    said = ' '.join(t for s in parsed()[0] for t in s['sentences'])
    assert '읽지 않는 설명 블록' not in said and '화면 진행' not in said


# ── trap 5: not every sentence ends with a period ──────────────────────────
def test_a_line_ending_on_a_sentence_ending_is_a_sentence():
    got = sentences(parsed()[0], '1')
    assert got.index('여기까지가 기본입니다') < got.index('이제 적용해 봅니다.')


def test_a_sentence_is_never_cut_where_the_pdf_did_not_break_the_line():
    """`...입니다 그리고...` on one line stays one cue, ending or no ending."""
    got = prompter.split_sentences('앞도 입니다 뒤도 입니다.')
    assert got == ['앞도 입니다 뒤도 입니다.']


# ── trap 6: the PDF splits a number from its particle ──────────────────────
def test_a_particle_is_glued_back_onto_its_number():
    got = sentences(parsed()[0], 'INTRO')
    assert '기간 20과 표준편차 2를 같이 봅니다.' in got


def test_a_number_followed_by_a_real_word_is_left_alone():
    assert prompter.split_sentences('기간 20 만큼 봅니다.') == ['기간 20 만큼 봅니다.']


# ── layout is configurable, nothing is hard-coded ──────────────────────────
def test_a_different_template_only_needs_a_different_layout():
    body = 'PART 1. 제목\n\n한 줄입니다.'
    assert prompter.parse(body)[0] == []
    mine = prompter.Layout(heading=re.compile(r'^PART (\d+)\.\s*(\S.*)$'))
    got, _ = prompter.parse(body, layout=mine)
    assert got == [{'section': '1', 'title': '제목', 'sentences': ['한 줄입니다.']}]


def test_the_worked_example_still_produces_its_recorded_output():
    """``examples/pdfform`` is the sample a reader runs first. Keep it true."""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'examples', 'pdfform')
    text = io.open(os.path.join(here, 'prompter_sample.txt'), encoding='utf-8').read()
    want = json.load(io.open(os.path.join(here, 'prompter_sample.json'), encoding='utf-8'))
    got, unresolved = prompter.parse(text)
    assert got == want and unresolved == []


def test_a_one_column_script_is_recognised_as_one():
    assert prompter.looks_single_column(TEXT)


def test_a_table_shaped_document_is_flagged_before_it_is_misread():
    """Two cells side by side land on one line and weld into a false sentence."""
    table = ('목차             내용\n'
             '1. 후킹          첫 칸의 글입니다.\n'
             '2. 소개          둘째 칸의 글입니다.\n'
             '3. 본론          셋째 칸의 글입니다.\n')
    assert not prompter.looks_single_column(table)


def test_reading_time_is_reported_per_section():
    got = dict(prompter.minutes(parsed()[0]))
    assert 0 < got['OUTRO'] < got['INTRO']


# ── poppler, and a PDF built here so the test owns no document ─────────────
YELLOW_RECT = '1 1 0 rg 100 600 200 50 re f'


def write_pdf(path, body=YELLOW_RECT):
    """A valid one-page Letter PDF with a real xref. Smallest honest fixture."""
    stream = body.encode('utf-8')
    objs = [b'<</Type/Catalog/Pages 2 0 R>>',
            b'<</Type/Pages/Kids[3 0 R]/Count 1>>',
            b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]'
            b'/Contents 4 0 R/Resources<<>>>>',
            b'<</Length %d>>stream\n%s\nendstream' % (len(stream), stream)]
    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        # `endstream` and `endobj` need whitespace between them, or poppler reads
        # `endstreamendobj` as an operator and renders a blank page, exit status 0.
        out += b'%d 0 obj\n' % i + obj + b'\nendobj\n'
    start = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for off in offsets:
        out += b'%010d 00000 n \n' % off
    out += b'trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, start)
    with open(path, 'wb') as f:
        f.write(bytes(out))
    return str(path)


@pytest.fixture(scope='module')
def have_poppler():
    try:
        poppler.tool('pdftoppm')
        poppler.tool('pdfinfo')
    except poppler.PopplerMissing as exc:
        pytest.skip(str(exc).splitlines()[0])


def test_a_missing_tool_says_how_to_install_it():
    with pytest.raises(poppler.PopplerMissing, match='winget'):
        poppler.tool('pdfdefinitelynotatool')


def test_page_size_is_measured_not_assumed(tmp_path, have_poppler):
    assert poppler.page_size(write_pdf(tmp_path / 'a.pdf')) == (612.0, 792.0)


def test_a_rendered_page_is_one_pixel_per_point_at_72_dpi(tmp_path, have_poppler):
    sheet = probe.render(write_pdf(tmp_path / 'a.pdf'), dpi=72)
    assert (sheet.width, sheet.height) == (612, 792)
    assert len(sheet.data) >= sheet.width * sheet.height * 3


def test_the_highlight_colour_is_read_off_the_pixels(tmp_path, have_poppler):
    """A settings dialog reports what was typed in; the page reports what is seen."""
    got = probe.fills(probe.render(write_pdf(tmp_path / 'a.pdf'), dpi=72))
    assert got and got[0]['rgb'] == '#FFFF00'
    assert got[0]['pixels'] == pytest.approx(200 * 50, rel=0.05)


def test_the_fill_is_located_on_the_page(tmp_path, have_poppler):
    """PDF counts y from the bottom, a raster from the top. 792 - 650 = 142."""
    left, top, right, bottom = probe.fills(
        probe.render(write_pdf(tmp_path / 'a.pdf'), dpi=72))[0]['box']
    assert (left, right) == pytest.approx((100, 299), abs=2)
    assert (top, bottom) == pytest.approx((142, 191), abs=2)


def test_white_paper_is_not_a_fill(tmp_path, have_poppler):
    assert probe.fills(probe.render(write_pdf(tmp_path / 'b.pdf', ''), dpi=72)) == []


def test_grey_is_not_a_fill(tmp_path, have_poppler):
    """Black text antialiases through grey, and so does a hairline rule."""
    grey = '0.5 g 100 600 200 50 re f'
    assert probe.fills(probe.render(write_pdf(tmp_path / 'c.pdf', grey), dpi=72)) == []


def test_margins_come_from_where_the_ink_actually_starts(tmp_path, have_poppler):
    got = probe.render(write_pdf(tmp_path / 'a.pdf'), dpi=72).margins_pt()
    assert got['left'] == pytest.approx(100, abs=2)
    assert got['top'] == pytest.approx(142, abs=2)


def test_a_blank_page_has_no_margins_to_measure(tmp_path, have_poppler):
    assert probe.render(write_pdf(tmp_path / 'b.pdf', ''), dpi=72).margins_pt() is None


def test_form_gathers_what_you_need_to_rebuild_the_template(tmp_path, have_poppler):
    got = probe.form(write_pdf(tmp_path / 'a.pdf'), dpi=72)
    assert got['pages'] == 1 and got['size_pt'] == (612.0, 792.0)
    assert got['fonts'] == []                      # a rectangle uses no font
    assert got['fills'][0]['rgb'] == '#FFFF00'


def test_a_ppm_header_may_carry_a_comment():
    blob = b'P6\n# written by something chatty\n2 1\n255\n' + bytes([1, 2, 3, 4, 5, 6])
    sheet = probe._read_ppm(blob)
    assert (sheet.width, sheet.height) == (2, 1)
    assert sheet.pixel(1, 0) == (4, 5, 6)


def test_something_that_is_not_a_ppm_is_rejected_loudly():
    with pytest.raises(ValueError, match='PPM'):
        probe._read_ppm(b'\x89PNG\r\n\x1a\n')
