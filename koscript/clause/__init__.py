# -*- coding: utf-8 -*-
"""Break Korean text at clause and phrase boundaries, not at a character count.

    >>> from koscript.clause import split
    >>> split("이 선이 방향을 확정해 줄 때까지 기다렸다가 그다음에 움직이는 방식입니다.")
    ['이 선이 방향을 확정해 줄 때까지 기다렸다가', '그다음에 움직이는 방식입니다.']

**Length is not the criterion.** Only grade 1 and 2 boundaries are used. ``long_at``
is a safety valve: if a segment comes out longer than that, grade-3 boundaries are
allowed *inside that segment only*, and the one nearest the middle is taken.

Aiming for a line length is what breaks Korean. The goal is the opposite -- break
less often, and make every break one a reader accepts.
"""
from . import model, rules, tagger
from .tagger import Tagger, strip_marks, visible_len

__all__ = ['split', 'boundaries', 'Tagger', 'model', 'rules', 'tagger',
           'strip_marks', 'visible_len', 'LONG_AT']

#: A segment longer than this may fall back to grade-3 boundaries.
LONG_AT = 40

_default = None


def _tagger(t=None):
    global _default
    if t is not None:
        return t
    if _default is None:
        _default = Tagger()
    return _default


def boundaries(text, tagger=None):
    """``{index: grade}`` for every gap between words. ``None`` = never break."""
    words = text.split()
    tg = _tagger(tagger)
    return {i: rules.grade(words, i, tg) for i in range(1, len(words))}


def split(text, long_at=LONG_AT, tagger=None):
    """Split one sentence into clause-level segments."""
    words = [w for w in text.split() if w]
    if not words:
        return []
    n = len(words)
    tg = _tagger(tagger)
    grades = {i: rules.grade(words, i, tg) for i in range(1, n)}

    def length(a, b):
        return visible_len(''.join(words[a:b]))

    cuts = [0] + [i for i in range(1, n)
                  if grades.get(i) is not None and grades[i] <= 2] + [n]
    spans = [(cuts[k], cuts[k + 1]) for k in range(len(cuts) - 1)]

    out = []
    for a, b in spans:
        if length(a, b) <= long_at:
            out.append((a, b))
            continue
        # 3급 가운데 **관형절(ETM) 뒤는 쓰지 않는다** — `매달 새로운 | 최신 보조지표와` 처럼
        # 꾸밈말과 꾸밈받는 말이 갈린다. 조사 뒤만 쓴다.
        inner = [i for i in range(a + 1, b)
                 if grades.get(i) is not None and grades[i] <= 3
                 and tg.last_tag(words[i - 1]) != 'ETM'
                 and not (tg.last_tag(words[i - 1]) == 'JKB'
                          and tg.first_tag(words[i]) in ('VV', 'VA', 'VX'))]
        if not inner:
            inner = [i for i in range(a + 1, b) if grades.get(i) is not None]
        if not inner:
            out.append((a, b))
            continue
        middle = (a + b) / 2.0
        at = min(inner, key=lambda i: abs(i - middle))
        out += [(a, at), (at, b)]
    return [' '.join(words[a:b]) for a, b in out]
