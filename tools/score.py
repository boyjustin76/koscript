# -*- coding: utf-8 -*-
"""Score a split against a human-edited reference.

**Precision is the number that matters** -- the share of *your* breaks that the
human also made. Recall rewards breaking more often, which is the wrong instinct.

The reference is one line of plain text per subtitle line. Neither file ships with
this repository; point the script at your own.

    python tools/score.py reference.txt [--no-kiwi]

With no second file the script splits the reference's own text and scores that --
that is, it asks "given the same sentences, do I break where the human did?"
"""
import argparse
import difflib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from koscript.clause import Tagger, split, strip_marks, visible_len  # noqa: E402

_THIN = re.compile(r'[\s+→·]')


def _bare(line):
    return _THIN.sub('', line)


def boundary_set(lines):
    """(joined text, set of character offsets where a line ended)"""
    text, cuts, run = '', set(), 0
    for l in lines:
        text += _bare(l)
        run += len(_bare(l))
        cuts.add(run)
    return text, cuts


def score(reference_lines, mine_lines):
    ref_text, ref_cuts = boundary_set(reference_lines)
    my_text, my_cuts = boundary_set(mine_lines)

    sm = difflib.SequenceMatcher(None, ref_text, my_text, autojunk=False)
    pair = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for d in range(i2 - i1 + 1):
                pair[i1 + d] = j1 + d
    back = {v: k for k, v in pair.items()}

    shared_ref = [i for i in ref_cuts if i in pair]
    hit = [i for i in shared_ref if pair[i] in my_cuts]
    shared_mine = [j for j in my_cuts if j in back]
    hit_mine = [j for j in shared_mine if back[j] in ref_cuts]

    extra = sorted(j for j in shared_mine if back[j] not in ref_cuts)
    return {
        'similarity': sm.ratio(),
        'recall': len(hit) / max(1, len(shared_ref)),
        'precision': len(hit_mine) / max(1, len(shared_mine)),
        'ref_lines': len(reference_lines), 'my_lines': len(mine_lines),
        'ref_chars': len(ref_text), 'my_chars': len(my_text),
        'extra': [(my_text[max(0, j - 14):j], my_text[j:j + 14]) for j in extra],
    }


def split_like_reference(reference_lines, tagger=None):
    """Re-split the reference's own sentences, so the comparison is like for like."""
    text = ' '.join(l.strip() for l in reference_lines)
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    out = []
    for s in sentences:
        out += split(s, tagger=tagger)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reference')
    ap.add_argument('mine', nargs='?')
    ap.add_argument('--kiwi', action='store_true')
    ap.add_argument('--show', type=int, default=12)
    a = ap.parse_args()

    ref = [l.strip() for l in io.open(a.reference, encoding='utf-8-sig').read().split('\n')
           if l.strip()]
    tg = Tagger(use_kiwi=a.kiwi)
    mine = ([l.strip() for l in io.open(a.mine, encoding='utf-8-sig').read().split('\n')
             if l.strip()] if a.mine else split_like_reference(ref, tg))

    r = score(ref, mine)
    print('reference %d lines / %d chars   mine %d lines / %d chars   kiwi=%s'
          % (r['ref_lines'], r['ref_chars'], r['my_lines'], r['my_chars'],
             'on' if a.kiwi else 'off'))
    print('  similarity %.4f' % r['similarity'])
    print('  recall     %.3f' % r['recall'])
    print('  PRECISION  %.3f' % r['precision'])
    if r['extra']:
        print('\n  broke where the human did not -- %d places' % len(r['extra']))
        for lo, hi in r['extra'][:a.show]:
            print('    ...%s | %s...' % (lo, hi))


if __name__ == '__main__':
    main()
