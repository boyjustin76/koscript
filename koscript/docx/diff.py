# -*- coding: utf-8 -*-
"""Compare two revisions **paragraph by paragraph**.

When a reviewed copy comes back, reading only the marks is not enough: there are
always edits made with no mark at all. In one real case a heading, three verb
endings and an episode number had been changed silently. Always diff the whole thing.
"""
import difflib

from . import read as _read


def diff(a_xml, b_xml, a_name='a', b_name='b', apply_marks=False, context=1):
    """Unified diff of the two paragraph lists.

    ``apply_marks`` compares them as they read *after* the reviewer's "delete this"
    marks are applied, so what is left is the genuine change.
    """
    a = _read.lines_after_marks(a_xml) if apply_marks else _read.lines(a_xml)
    b = _read.lines_after_marks(b_xml) if apply_marks else _read.lines(b_xml)
    return list(difflib.unified_diff(a, b, a_name, b_name, lineterm='', n=context))


def changed_lines(a_xml, b_xml, apply_marks=False):
    """``(removed, added)`` -- when you just want the counts and the text."""
    out = diff(a_xml, b_xml, apply_marks=apply_marks, context=0)
    removed = [l[1:] for l in out if l.startswith('-') and not l.startswith('---')]
    added = [l[1:] for l in out if l.startswith('+') and not l.startswith('+++')]
    return removed, added
