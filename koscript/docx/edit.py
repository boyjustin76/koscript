# -*- coding: utf-8 -*-
"""Edit ``word/document.xml`` -- **counting what you changed.**

The usual accident when editing a form is that a second, unintended place changes
too. So every replacement asserts how many matches it found and refuses to guess.

Cells holding only whitespace cannot be addressed by string at all; use
``replace_paragraph`` with an index.
"""
import re

from . import read as _read


def replace_once(body_xml, old, new):
    """Replace ``old`` only if it occurs exactly once. Raises otherwise."""
    n = body_xml.count(old)
    if n != 1:
        raise ValueError('found %d occurrences, expected exactly 1: %r' % (n, old[:70]))
    return body_xml.replace(old, new)


def replace_all_once(body_xml, pairs):
    """Apply ``[(old, new)]`` in order. If any one is not unique, **nothing** changes."""
    s = body_xml
    for old, new in pairs:
        s = replace_once(s, old, new)
    return s


def replace_paragraph(body_xml, index, new_paragraph_xml):
    """Swap one whole paragraph, addressed by its index in ``read.paragraphs``.

    Use this when runs are split too finely to address by string. Carry the original
    opening tag and ``<w:pPr>`` over with ``paragraph_head`` to keep the formatting.
    """
    old = _read.paragraphs(body_xml)[index]
    return replace_once(body_xml, old, new_paragraph_xml)


def paragraph_head(paragraph_xml):
    """A paragraph's opening tag plus its ``<w:pPr>`` -- to inherit its formatting."""
    m = re.match(r'(<w:p\b[^>]*>)(<w:pPr>.*?</w:pPr>)?', paragraph_xml, re.S)
    return m.group(1) + (m.group(2) or '')


def assert_text(body_xml, absent=(), present=()):
    """Guard rail after editing: nothing from ``absent`` left, everything in ``present`` in."""
    text = '\n'.join(_read.lines(body_xml))
    left = [w for w in absent if w in text]
    missing = [w for w in present if w not in text]
    if left or missing:
        raise ValueError('still present %r / missing %r' % (left, missing))
    return True
