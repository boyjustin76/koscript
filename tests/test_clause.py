# -*- coding: utf-8 -*-
"""clause tests.

The rules are what we can test without the corpus: feed a tagger whose answers we
control, and assert that the forbidden places stay forbidden. Tests needing the real
table skip when it is not there.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from koscript import clause                      # noqa: E402
from koscript.clause import model, rules         # noqa: E402
from koscript.clause.tagger import Tagger, strip_marks, visible_len   # noqa: E402

HAVE_TABLE = model.load()['words'] != {}
needs_table = pytest.mark.skipif(not HAVE_TABLE, reason='no corpus table -- see docs/SETUP.md')


class FakeTagger:
    """Answers come from dicts, so a rule can be tested on its own."""

    def __init__(self, first=None, last=None, aux=(), bound=()):
        self._first, self._last = first or {}, last or {}
        self._aux, self._bound = set(aux), set(bound)

    def first_tag(self, w):
        return self._first.get(strip_marks(w))

    def last_tag(self, w):
        return self._last.get(strip_marks(w))

    def is_aux_verb(self, w):
        return strip_marks(w) in self._aux

    def is_bound_noun(self, w):
        return strip_marks(w) in self._bound


def grade_between(a, b, **kw):
    return rules.grade([a, b, 'xx'], 1, FakeTagger(**kw))


# ── length is not a criterion ──────────────────────────────────────────────
def test_visible_length_ignores_spaces_and_thin_glyphs():
    assert visible_len('밴드 확장 + 강한 장대봉') == len('밴드확장강한장대봉')


def test_strip_marks_removes_punctuation():
    assert strip_marks('"더블' ) == '더블'
    assert strip_marks('불구하고,') == '불구하고'


# ── forbidden places ───────────────────────────────────────────────────────
def test_never_after_a_one_syllable_determiner():
    assert grade_between('두', '개를') is None          # `두 | 개를`


def test_never_after_the_genitive_particle():
    assert grade_between('밴드의', '하단', last={'밴드의': 'JKG'}) is None


def test_never_before_an_auxiliary_verb():
    assert grade_between('알려', '주는', last={'알려': 'EC_AUX'}, aux=['주는']) is None


def test_never_before_a_bound_noun():
    assert grade_between('확대될', '수', last={'확대될': 'ETM'}, bound=['수']) is None


def test_never_before_a_dependent_verb():
    assert grade_between('매수했음에도', '불구하고', last={'매수했음에도': 'JKB'}) is None


def test_never_before_an_adverb():
    """사람은 거꾸로 부사 **뒤**에서 끊는다."""
    assert grade_between('트레이더가', '가장', last={'트레이더가': 'JKS'},
                         first={'가장': 'MAG'}) is None


def test_never_after_a_conjunctive_particle():
    assert grade_between('캔들과', '밴드', last={'캔들과': 'JKB'}) is None


def test_never_before_the_copula():
    assert grade_between('하나가', '아닌', last={'하나가': 'JKC'}, first={'아닌': 'VCN'}) is None


def test_never_inside_a_compound_noun():
    assert grade_between('경고', '신호로', last={'경고': 'NNG'}, first={'신호로': 'NNG'}) is None


def test_never_inside_quotes():
    words = ['‘겹쳐', '보기', '방법’']
    assert rules.grade(words, 1, FakeTagger()) is None


# ── allowed places, by grade ───────────────────────────────────────────────
def test_punctuation_is_grade_one_and_beats_everything():
    """구두점을 뒤에 보면 복합명사 금지에 먹힌다 — `기간 20, | 표준편차` 가 막혔다."""
    words = ['대부분의', '설정은', '기간', '20,', '표준편차']
    g = rules.grade(words, 4, FakeTagger(last={'20': 'SN'}, first={'표준편차': 'NNG'}))
    assert g == 1


def test_no_break_right_after_the_opening_word():
    """`단,` `첫째,` 를 떼면 한 어절만 뜬 줄이 된다."""
    assert rules.grade(['첫째,', '중심선이', 'xx'], 1, FakeTagger()) is None


def test_sentence_ending_is_grade_two():
    assert grade_between('달라집니다', '하지만', last={'달라집니다': 'EF'}) == 2
    # 구두점이 있으면 1급 — 단, 문장 머리(2어절 이내)가 아닐 때
    words = ['가격이', '강한', '방향성을', '달라집니다.', '하지만']
    assert rules.grade(words, 4, FakeTagger(last={'달라집니다': 'EF'})) == 1


def test_only_clause_closing_endings_are_grade_two():
    assert grade_between('형성하면', '문제가', last={'형성하면': 'EC'}) == 2
    # `-게` 는 절을 닫지 않는다 — 뒤의 용언·목적어와 한 덩어리다
    assert grade_between('타이트하게', '손절선을', last={'타이트하게': 'EC'}) == 3


def test_particles_are_grade_three():
    assert grade_between('가격이', '밴드를', last={'가격이': 'JKS'}) == 3


# ── split() ────────────────────────────────────────────────────────────────
def test_split_uses_only_grade_one_and_two():
    tg = FakeTagger(last={'가격이': 'JKS', '달라집니다': 'EF'})
    assert clause.split('가격이 크게 달라집니다 그래서', tagger=tg) == \
        ['가격이 크게 달라집니다', '그래서']


def test_grade_three_only_rescues_a_very_long_segment():
    text = ' '.join(['가격이'] * 20)
    tg = FakeTagger(last={'가격이': 'JKS'})
    assert len(clause.split(text, long_at=1000, tagger=tg)) == 1
    assert len(clause.split(text, long_at=10, tagger=tg)) == 2


def test_split_of_empty_text():
    assert clause.split('   ') == []


# ── with the real corpus table ─────────────────────────────────────────────
@needs_table
def test_real_table_keeps_an_auxiliary_verb_attached():
    """`알려 | 주는` -- a main verb cut from its auxiliary. The original bug."""
    out = clause.split('지금 날씨가 평소와 얼마나 다른지를 숫자로 알려 주는 '
                       '하나의 기준일 뿐입니다')
    assert not any(seg.endswith('알려') for seg in out)


@needs_table
def test_real_table_does_not_split_a_quoted_name_or_a_determiner():
    out = clause.split('오늘은 이것을 하나가 아닌 두 개를 겹쳐 쓰는 '
                       '‘겹쳐 보기’ 방법을 통해, 그 차이를 알려드리겠습니다')
    assert not any(seg.rstrip().endswith('‘겹쳐') for seg in out)
    assert not any(seg.rstrip().endswith('두') for seg in out)
    assert not any(seg.rstrip().endswith('하나가') for seg in out)   # `| 아닌`


@needs_table
def test_model_info_reports_what_is_loaded():
    got = model.info()
    assert got['word_forms'] > 0 and got['path']


def test_model_error_names_the_paths_it_tried(tmp_path, monkeypatch):
    monkeypatch.setenv(model.ENV_VAR, str(tmp_path / 'nope.json.gz'))
    # 기본 경로에 진짜 표가 있으면 그걸 집어 온다 — 그것도 치워야 '없을 때' 를 시험한다
    monkeypatch.setattr(model, 'DEFAULT_PATH', str(tmp_path / 'also-nope.json.gz'))
    model.clear_cache()
    with pytest.raises(FileNotFoundError) as e:
        model.load(required=True)
    assert 'nope.json.gz' in str(e.value) and 'SETUP.md' in str(e.value)
    model.clear_cache()


def test_tagger_works_without_kiwi_installed():
    tg = Tagger(table=dict(model.EMPTY), use_kiwi=False)
    assert tg.last_tag('달라집니다') == 'EF'      # falls through to the suffix rules
