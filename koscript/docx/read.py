# -*- coding: utf-8 -*-
"""Read text and **a reviewer's marks** out of ``word/document.xml``.

A reviewed document usually comes back marked: strikethrough for "delete this",
underline for "I replaced it with this", a colour for "keep this". Tools that
extract plain text throw all of that away -- and the marks *are* the work.
So runs are read together with their formatting.

Word splits one sentence across many ``<w:r>`` runs (spell-check state, revision
ids). A phrase you can see in the document often does not exist as a contiguous
string in the XML.
"""
import re

_PARA = re.compile(r'<w:p\b[^>]*>.*?</w:p>|<w:p\b[^>]*/>', re.S)
_RUN = re.compile(r'<w:r\b[^>]*>(.*?)</w:r>', re.S)
_RPR = re.compile(r'<w:rPr>.*?</w:rPr>', re.S)
# `<w:t ...>` only. `<w:t[^>]*>` also matches `<w:tbl>` and `<w:tc>`, which spills
# raw XML into the extracted text -- a real bug that shipped once.
_TEXT = re.compile(r'<w:t(?: [^>]*)?>(.*?)</w:t>', re.S)
_CELL = re.compile(r'<w:tc>.*?</w:tc>', re.S)

DEFAULT_MARKS = {'strike': ('[-', '-]'), 'underline': ('[_', '_]')}


def unescape(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&'))


def paragraphs(body_xml):
    """Paragraph XML fragments, in document order."""
    return _PARA.findall(body_xml)


def text_of(fragment):
    """Visible text of a paragraph or cell fragment."""
    return unescape(''.join(_TEXT.findall(fragment)))


def lines(body_xml, drop_empty=True):
    """One string per paragraph, table paragraphs included, in order."""
    out = [text_of(p) for p in paragraphs(body_xml)]
    return [t for t in out if t.strip()] if drop_empty else out


def cells(body_xml):
    """One string per table cell. Form documents are fastest to address by index."""
    return [text_of(c) for c in _CELL.findall(body_xml)]


def runs(paragraph_xml):
    """``[(text, fmt)]`` -- fmt has bold/italic/strike/underline/color/fill."""
    out = []
    for r in _RUN.findall(paragraph_xml):
        m = _RPR.search(r)
        rpr = m.group(0) if m else ''
        t = unescape(''.join(_TEXT.findall(r)))
        if not t:
            continue
        color = re.search(r'<w:color w:val="([0-9A-Fa-f]{6})"', rpr)
        fill = re.search(r'w:fill="([0-9A-Fa-f]{6})"', rpr)
        out.append((t, {
            'bold': '<w:b/>' in rpr or '<w:b ' in rpr,
            'italic': '<w:i/>' in rpr or '<w:i ' in rpr,
            'strike': '<w:strike' in rpr,
            'underline': '<w:u ' in rpr or '<w:u/>' in rpr,
            'color': color.group(1).upper() if color else None,
            'fill': fill.group(1).upper() if fill else None,
        }))
    return out


def read_marks(body_xml, marks=None):
    """Surface a reviewer's marks inline.

    ``marks`` maps a format name to a ``(left, right)`` pair; the default is
    strikethrough ``[-...-]`` and underline ``[_..._]``. To key on a value, use
    ``{'color:EE0000': ('[+', '+]')}``.

    Returns ``[(paragraph_index, marked_text)]`` for **marked paragraphs only**.
    A run carrying two marks is tagged with the first one that matches.
    """
    marks = marks or DEFAULT_MARKS
    out = []
    for i, p in enumerate(paragraphs(body_xml)):
        parts, found = [], False
        for t, fmt in runs(p):
            wrap = None
            for name, (lo, hi) in marks.items():
                key, _, want = name.partition(':')
                if (fmt.get(key) == want) if want else bool(fmt.get(key)):
                    wrap = (lo, hi)
                    break
            parts.append(wrap[0] + t + wrap[1] if wrap else t)
            found = found or wrap is not None
        if found:
            out.append((i, ''.join(parts)))
    return out


def lines_after_marks(body_xml, drop='strike'):
    """Lines as they read once the "delete this" marks are actually applied."""
    out = []
    for p in paragraphs(body_xml):
        t = ''.join(t for t, fmt in runs(p) if not fmt.get(drop)).strip()
        if t:
            out.append(t)
    return out
