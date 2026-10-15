# -*- coding: utf-8 -*-
"""Where may a line break, and how good is that place?

Every gap between two words gets a grade. ``None`` means **never break here**.

    1  after punctuation      -- always take it
    2  after a sentence ending, or a connective ending that closes a clause
    3  after a particle or an adnominal ending -- **last resort only**
    4  anything else          -- avoid

Grade 3 exists only to rescue a segment that came out very long. Breaking at
grade 3 to hit a character target is what produces ``오르는 | 경우도`` and
``확정하는 | 선이`` -- grammatical in isolation, wrong to read.

Punctuation is checked **first**, before the forbidden rules. Put it later and the
compound-noun rule swallows it: ``기간 20, | 표준편차`` gets blocked even though a
comma is the most reliable break there is.
"""
import re

from .tagger import strip_marks

# 체언 태그 — 복합명사를 가르지 않으려고 본다
NOUNISH = ('NNG', 'NNP', 'SL', 'SN', 'NR', 'XSN', 'XR')

# 한 글자 관형사 — `두 | 개를`, `이 | 검정색` 을 막는다
DETERMINERS = {'두', '한', '세', '네', '다섯', '여섯', '몇', '여러', '각', '이', '그', '저',
               '매', '온', '전', '새', '첫', '옛', '약', '총', '뭐', '무슨', '어떤', '모든'}

# 앞의 체언 없이는 못 서는 용언 — `~에도 불구하고`, `~에 비해`, `~을 통해`
DEPENDENT_VERBS = {
    '불구하고', '불구하여', '비해', '비하여', '대해', '대하여', '대한', '위해', '위하여', '위한',
    '통해', '통하여', '통한', '관해', '관하여', '관한', '의해', '의하여', '의한',
    '따라', '따라서는', '달리', '있어', '있어서', '한하여', '제외하고', '비롯한', '비롯해',
    '대비', '기준으로', '한해'}

# **절을 닫는** 연결어미만 2급이다. `-게`(부사형)와 `-아/어/여`(보조적)는 들어가지 않는다 —
# 절을 닫지 않고 뒤의 용언·목적어와 한 덩어리로 읽힌다 (`타이트하게 | 손절선을` 을 막는다).
CLAUSE_CLOSING = re.compile(
    r'(고|며|면|면서|지만|는데|은데|ㄴ데|니까|거나|더라도|도록|므로|다가'
    r'|라면|다면|든지|고자|려고|으며|으면|으니|으므로|자|지라도)$')

_AUX_LINKING_END = re.compile(r'(아|어|여|려|워|해|야|게|지|고|기)$')
_PUNCT_END = re.compile(r'[.?!…,;:]$')
_PAIRS = (('‘', '’'), ('“', '”'), ('(', ')'), ('[', ']'))


def _inside_quotes(words, i):
    text = ' '.join(words[:i])
    for lo, hi in _PAIRS:
        if text.count(lo) > text.count(hi):
            return True
    for q in ("'", '"'):
        if text.count(q) % 2:
            return True
    return False


def grade(words, i, tagger):
    """Grade of the gap before ``words[i]``. ``None`` = do not break here."""
    left, right = words[i - 1], words[i]
    left_form = strip_marks(left)
    right_form = strip_marks(right)

    # 1급 — 구두점 뒤. 무엇보다 먼저 본다.
    if _PUNCT_END.search(left.strip()):
        if not _inside_quotes(words, i):
            # 문장 머리의 짧은 접속·순서말 뒤는 끊지 않는다 — `단,` `첫째,`.
            # 떼면 한 어절만 떠 있는 줄이 된다.
            if i > 2:
                return 1

    if _inside_quotes(words, i):
        return None

    left_tag, right_tag = tagger.last_tag(left), tagger.last_tag(right)
    right_first = tagger.first_tag(right)

    # ── 끊으면 안 되는 자리 ─────────────────────────────────────────────
    if left_form in DETERMINERS:
        return None
    # 관형사 태그는 MM·MMD·MMA·MMN 으로 갈린다 — 앞가지로 한꺼번에 막는다
    if left_tag and (left_tag.startswith('MM')
                     or left_tag in ('JKG', 'ETN', 'NNB', 'XPN', 'MAJ')):
        return None
    if tagger.is_bound_noun(right):
        return None                      # `두 | 개를`, `확대될 | 수 있다는`
    if right_form in DEPENDENT_VERBS:
        return None                      # `매수했음에도 | 불구하고`
    if tagger.is_aux_verb(right) and (left_tag in ('EC', 'EC_AUX', 'ETN')
                                      or _AUX_LINKING_END.search(left_form)):
        return None                      # `알려 | 주는`, `받아들여야 | 합니다`
    # 부사 **앞**에서는 끊지 않는다 — 부사는 뒤의 용언과 한 덩어리다.
    # 사람은 거꾸로 부사 **뒤**에서 끊는다 (`모두 | 밴드에`, `절대 | 매매를`).
    if right_first in ('MAG', 'MAJ'):
        return None
    # 접속조사 뒤 — 말뭉치가 `-와/과` 를 부사격(JKB)으로 태깅해서 글자꼴로 본다
    if left_tag == 'JC' or re.search(r'[가-힣](와|과)$', left_form):
        return None
    # `아니다`(VCN)·`이다`(VCP) 는 앞의 보어와 한 덩어리다 — `하나가 | 아닌`
    if right_first in ('VCN', 'VCP') or re.match(r'^(아니|아닌|아니라|아닙니다|이라는|이라고)',
                                                 right_form):
        return None
    # 복합명사 사이 — `경고 | 신호로`, `손절 | 폭이`.
    # 태그를 못 찾은 말은 **어미로 끝나지 않을 때만** 체언으로 본다. 그냥 체언으로 몰면
    # `닿아 | 매수했음에도` 까지 막히고, 빼면 복합명사가 갈린다. 둘 다 겪었다.
    left_nounish = left_tag in NOUNISH or (
        left_tag is None and not re.search(r'[아어여고며면니지게기야요다서워해]$', left_form))
    if left_nounish and (right_first in NOUNISH or right_first is None):
        return None

    # ── 끊어도 되는 자리 ───────────────────────────────────────────────
    if left_tag == 'EF':
        return 2
    if left_tag in ('EC', 'EC_CLOSE') and CLAUSE_CLOSING.search(left_form):
        return 2
    if left_tag in ('ETM', 'JX', 'JKB', 'JKS', 'JKO', 'JKC', 'EC', 'EC_CLOSE', 'EC_AUX'):
        return 3
    return 4
