# -*- coding: utf-8 -*-
"""Load the corpus-derived lookup table, and say clearly when it is missing.

The table maps Korean word forms to the part-of-speech tags they start and end
with, built from the NIKL morpheme-analysed corpus. It is **not** in this
repository -- the corpus terms forbid redistributing anything derived from it.
Build your own with ``python -m koscript.clause.build_tags`` (see docs/SETUP.md).
"""
import gzip
import json
import os

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data',
                            'ko_tags.json.gz')
ENV_VAR = 'KOSCRIPT_TAGS'

EMPTY = {'words': {}, 'suffixes': {}, 'prefixes': {}, 'aux_verbs': [], 'bound_nouns': []}

# 옛 빌더가 낸 한국어 키 — 이미 만들어 둔 표를 버리지 않으려고 받아 준다
_LEGACY_KEYS = {'어절': 'words', '끝꼴': 'suffixes', '앞꼴': 'prefixes',
                '보조용언': 'aux_verbs', '의존명사': 'bound_nouns'}

_cache = None
_cache_path = None


def search_paths():
    """Where ``load()`` looks, in order."""
    out = []
    if os.environ.get(ENV_VAR):
        out.append(os.environ[ENV_VAR])
    out.append(DEFAULT_PATH)
    return out


def load(path=None, required=False):
    """Return the table. Falls back to an empty one unless ``required``."""
    global _cache, _cache_path
    candidates = [path] if path else search_paths()
    for p in candidates:
        if p == _cache_path and _cache is not None:
            return _cache
        if p and os.path.exists(p):
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                raw = json.load(f)
            table = {_LEGACY_KEYS.get(k, k): v for k, v in raw.items()}
            for k, v in EMPTY.items():
                table.setdefault(k, type(v)())
            _cache, _cache_path = table, p
            return table
    if required:
        raise FileNotFoundError(
            'corpus table not found. Looked at:\n  ' + '\n  '.join(candidates)
            + '\n\nBuild it from the NIKL corpus:\n'
              '  python -m koscript.clause.build_tags <corpus folder> ' + DEFAULT_PATH
            + '\nor point ' + ENV_VAR + ' at an existing one.\n'
              'How to obtain the corpus: docs/SETUP.md')
    return dict(EMPTY)


def info(path=None):
    """What is loaded -- call this first when results look wrong."""
    table = load(path)
    return {
        'path': _cache_path,
        'searched': search_paths(),
        'word_forms': len(table['words']),
        'suffixes': len(table['suffixes']),
        'prefixes': len(table['prefixes']),
        'aux_verbs': len(table['aux_verbs']),
        'bound_nouns': len(table['bound_nouns']),
    }


def clear_cache():
    global _cache, _cache_path
    _cache, _cache_path = None, None
