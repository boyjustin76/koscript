# -*- coding: utf-8 -*-
"""Property checks against **real** ``.docx`` files.

Passing on a document you built yourself proves little. Word splits runs in ways no
generator reproduces, so the library has to hold up on files a person actually edited.

Point ``KOSCRIPT_FIXTURES`` at a folder of ``.docx`` files and these run against every
one of them. No file is named here and none ships with the repository -- use your own.

    KOSCRIPT_FIXTURES=~/some/documents python -m pytest tests/test_real_documents.py
"""
import glob
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from koscript.docx import build, diff, edit, pack, read   # noqa: E402

FIXTURES = os.environ.get('KOSCRIPT_FIXTURES')


def _documents():
    if not FIXTURES or not os.path.isdir(FIXTURES):
        return []
    found = glob.glob(os.path.join(FIXTURES, '**', '*.docx'), recursive=True)
    return sorted(p for p in found if not os.path.basename(p).startswith('~$'))


DOCS = _documents()
pytestmark = pytest.mark.skipif(
    not DOCS, reason='set KOSCRIPT_FIXTURES to a folder containing .docx files')


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
