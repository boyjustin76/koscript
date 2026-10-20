# -*- coding: utf-8 -*-
"""Property checks against **real** ``.docx`` and ``.pdf`` files.

Passing on a document you built yourself proves little. Word splits runs in ways no
generator reproduces, and a PDF written by Word wraps lines in ways no fixture
imitates, so the library has to hold up on files a person actually edited.

Point ``KOSCRIPT_FIXTURES`` at a folder and these run against every document in it.
No file is named here and none ships with the repository -- use your own.

    KOSCRIPT_FIXTURES=~/some/documents python -m pytest tests/test_real_documents.py
"""
import glob
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from koscript.docx import build, diff, edit, pack, read   # noqa: E402
from koscript.pdfform import poppler, prompter            # noqa: E402

FIXTURES = os.environ.get('KOSCRIPT_FIXTURES')


def _documents(ext):
    if not FIXTURES or not os.path.isdir(FIXTURES):
        return []
    found = glob.glob(os.path.join(FIXTURES, '**', '*.' + ext), recursive=True)
    return sorted(p for p in found if not os.path.basename(p).startswith('~$'))


DOCS = _documents('docx')
PDFS = _documents('pdf')
pytestmark = pytest.mark.skipif(
    not DOCS and not PDFS,
    reason='set KOSCRIPT_FIXTURES to a folder containing .docx or .pdf files')


def _ids(paths):
    return [os.path.basename(p)[:28] for p in paths]


@pytest.fixture(params=DOCS, ids=_ids(DOCS))
def doc(request, tmp_path):
    return pack.unpack(request.param, str(tmp_path / 'src'))


def test_round_trip_does_not_touch_a_single_byte(doc, tmp_path):
    original = pack.read_body(doc)
    again = pack.unpack(pack.repack(doc, str(tmp_path / 'again.docx')), str(tmp_path / 'src2'))
    assert pack.read_body(again) == original


def test_no_markup_leaks_into_extracted_text(doc):
    """`<w:t[^>]*>` also matches `<w:tbl>`; raw XML then shows up as a 'line'."""
    for line in read.lines(pack.read_body(doc)):
        assert '<w:' not in line, line[:80]


def test_marked_paragraphs_really_carry_a_mark(doc):
    for _, text in read.read_marks(pack.read_body(doc)):
        assert '[-' in text or '[_' in text


def test_applying_marks_only_removes_text(doc):
    """Dropping struck runs must never *add* anything."""
    body = pack.read_body(doc)
    before = ''.join(read.lines(body))
    after = ''.join(read.lines_after_marks(body))
    assert len(after) <= len(before)


def test_a_document_does_not_differ_from_itself(doc):
    body = pack.read_body(doc)
    removed, added = diff.changed_lines(body, body)
    assert (removed, added) == ([], [])


def test_diff_reports_an_edit_in_both_directions(doc):
    """Edit through ``replace_paragraph``, not through the extracted text.

    Searching for a line you *read* and replacing it in the XML fails on real files:
    Word has split that sentence across runs, so the string is not there. This test
    walked into exactly that -- which is the reason ``replace_paragraph`` exists.
    """
    body = pack.read_body(doc)
    paras = read.paragraphs(body)
    i = next((n for n, p in enumerate(paras) if read.text_of(p).strip()), None)
    if i is None:
        pytest.skip('no text in this document')

    was = read.text_of(paras[i])
    edited = edit.replace_paragraph(
        body, i, edit.paragraph_head(paras[i]) + build.run(was + ' EDITED') + '</w:p>')
    removed, added = diff.changed_lines(body, edited)
    assert any(l.endswith('EDITED') for l in added)
    assert was in removed


# ── prompter PDFs ──────────────────────────────────────────────────────────
@pytest.fixture(params=PDFS, ids=_ids(PDFS))
def script_pdf(request):
    try:
        poppler.tool('pdftotext')
    except poppler.PopplerMissing as exc:
        pytest.skip(str(exc).splitlines()[0])
    if not prompter.looks_single_column(poppler.text(request.param)):
        pytest.skip('not a one-column document -- prompter is the wrong reader for it')
    return request.param


def test_no_page_furniture_is_read_aloud(script_pdf):
    """Whatever repeats at the rim of every page is not part of the script."""
    text = poppler.text(script_pdf)
    sections, _ = prompter.parse(text)
    said = ' '.join(t for s in sections for t in s['sentences'])
    for line in prompter.page_furniture(text):
        assert line not in said, line


def test_no_sentence_is_cut_at_a_line_wrap(script_pdf):
    """Trap 1 leaves a signature: a quote or a bracket opened and never closed.

    The cue that shipped wrong was ``... 겹쳐 사용하는 '더블`` -- the other half of
    the quoted phrase had become a second cue. Requiring a sentence ending here
    instead would be wrong: an outline or a bracketed to-do list is not a
    sentence, and those are legitimately in a script.
    """
    sections, _ = prompter.read(script_pdf)
    for s in sections:
        for t in s['sentences']:
            for pair in ('()', '[]', '“”', '‘’'):
                assert t.count(pair[0]) == t.count(pair[1]), t[-50:]
            for quote in ('\'', '"'):
                assert t.count(quote) % 2 == 0, t[-50:]


def test_a_number_never_keeps_a_space_before_its_particle(script_pdf):
    sections, _ = prompter.read(script_pdf)
    for s in sections:
        for t in s['sentences']:
            assert not prompter.PARTICLE_AFTER_NUMBER.search(t), t


def test_the_section_titles_do_not_leak_into_the_spoken_lines(script_pdf):
    sections, _ = prompter.read(script_pdf)
    for s in sections:
        if len(s['title']) > 6:
            assert s['title'] not in ' '.join(s['sentences'])
