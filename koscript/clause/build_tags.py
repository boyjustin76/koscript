# -*- coding: utf-8 -*-
"""Build the lookup table from the NIKL morpheme-analysed corpus (모두의 말뭉치 형태 분석).

    python -m koscript.clause.build_tags <corpus folder or .json files> [-o out.json.gz]

The corpus is not in this repository and may not be redistributed -- see docs/SETUP.md
for how to apply for it. This script turns it into the table ``clause`` reads.

What comes out:

    words        the word form itself -> [first tag, last tag, count]  (the real answer)
    suffixes     last 2-5 characters  -> most common final tag         (for unseen forms)
    prefixes     first 2-4 characters -> most common initial tag
    aux_verbs    forms actually tagged VX in the corpus
    bound_nouns  forms actually tagged NNB

**One-character affixes are not kept.** They are too ambiguous and produce confident
wrong answers: ``경고`` read as ending in ``고`` (a connective ending), ``객관적인`` as
ending in ``인`` (a noun). Both put line breaks in the wrong place.
"""
import argparse
import glob
import gzip
import io
import json
import os
from collections import Counter, defaultdict

MAX_SUFFIX, MIN_SUFFIX = 5, 2       # 1글자 꼴은 안 쓴다
MAX_PREFIX, MIN_PREFIX = 4, 2
MIN_COUNT = 3                       # 이보다 드문 꼴은 버린다 (크기·잡음)
MIN_WORD_COUNT = 1                  # 어절 사전은 한 번 나온 것도 담는다 — 진본이라서


def _json_files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, '**', '*.json'), recursive=True))
        else:
            out.append(p)
    return out


def collect(paths):
    words = defaultdict(Counter)
    suffix = defaultdict(Counter)
    prefix = defaultdict(Counter)
    aux, bound = Counter(), Counter()
    seen = 0

    for path in _json_files(paths):
        try:
            data = json.load(io.open(path, encoding='utf-8'))
        except Exception:
            continue
        for doc in data.get('document', []):
            for sent in doc.get('sentence', []):
                morphemes = sent.get('MP') or []
                if not morphemes:
                    continue
                chunks = defaultdict(list)
                for m in morphemes:
                    chunks[m['word_id']].append((m.get('position', 0), m['form'], m['label']))
                for parts in chunks.values():
                    parts.sort()
                    form = ''.join(f for _, f, _ in parts)
                    if not form:
                        continue
                    seen += 1
                    first, last = parts[0][2], parts[-1][2]
                    words[form][(first, last)] += 1
                    for k in range(MIN_SUFFIX, MAX_SUFFIX + 1):
                        if len(form) > k:
                            suffix[form[-k:]][last] += 1
                    for k in range(MIN_PREFIX, MAX_PREFIX + 1):
                        if len(form) > k:
                            prefix[form[:k]][first] += 1
                    for _, f, label in parts:
                        if label == 'VX':
                            aux[f] += 1
                        elif label == 'NNB':
                            bound[f] += 1
    return words, suffix, prefix, aux, bound, seen


def _dominant(counter):
    """(tag, purity, count) -- purity is how often the top tag wins."""
    total = sum(counter.values())
    tag, n = counter.most_common(1)[0]
    return [tag, round(n / total, 3), total]


def build(paths, out_path):
    words, suffix, prefix, aux, bound, seen = collect(paths)
    table = {
        'words': {w: [c.most_common(1)[0][0][0], c.most_common(1)[0][0][1], sum(c.values())]
                  for w, c in words.items() if sum(c.values()) >= MIN_WORD_COUNT},
        'suffixes': {k: _dominant(c) for k, c in suffix.items() if sum(c.values()) >= MIN_COUNT},
        'prefixes': {k: _dominant(c) for k, c in prefix.items() if sum(c.values()) >= MIN_COUNT},
        'aux_verbs': [w for w, n in aux.most_common() if n >= MIN_COUNT],
        'bound_nouns': [w for w, n in bound.most_common() if n >= MIN_COUNT],
        'built_from': 'NIKL morpheme-analysed corpus (not redistributable)',
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    with gzip.open(out_path, 'wt', encoding='utf-8') as f:
        json.dump(table, f, ensure_ascii=False)
    return table, seen


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('corpus', nargs='+', help='folder of, or paths to, NIKL MP .json files')
    ap.add_argument('-o', '--out', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'data', 'ko_tags.json.gz'))
    a = ap.parse_args()

    table, seen = build(a.corpus, a.out)
    if not table['words']:
        raise SystemExit(
            'no word forms found. Are these NIKL MP files? Each should contain\n'
            '  document[].sentence[].MP[] with form / label / word_id\n'
            'See docs/SETUP.md for which corpus to apply for.')
    size = os.path.getsize(a.out) / 1024
    print('%s\n  %d word forms from %d tokens · %d suffixes · %d prefixes '
          '· %d aux verbs · %d bound nouns · %.0f KB'
          % (a.out, len(table['words']), seen, len(table['suffixes']),
             len(table['prefixes']), len(table['aux_verbs']),
             len(table['bound_nouns']), size))


if __name__ == '__main__':
    main()
