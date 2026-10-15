# -*- coding: utf-8 -*-
"""Which part of speech does a word form start and end with?

Three sources, in order of trust:

1. **The corpus table.** A word form seen in the corpus carries its real tags.
   This is the only source that settles the cases that matter -- ``설정은``
   (noun + particle) and ``깊은`` (verb + adnominal ending) both end in ``은``,
   and only frequency data tells them apart.
2. **Kiwi.** For a form the corpus never saw -- a loanword, a proper noun, a
   coinage -- an analyzer still produces a usable tag.
3. **Suffix patterns.** Last resort, pure character shape.

**One-character suffixes are never used.** They are too ambiguous: ``경고`` read
as ending in ``고`` (a connective ending) and ``객관적인`` as ending in ``인``
(a noun), and both produced breaks in the wrong place.
"""
import re

from . import model

_NOISE = re.compile(r"""[\s'"‘’“”.,!?()\[\]/·…~\-+:;]""")

# 글자 수를 셀 때 공백과 가느다란 기호는 안 센다 — 화면에서 폭을 거의 안 먹는다
_THIN = re.compile(r'[\s+→·]')

# 말뭉치에도 Kiwi 에도 없을 때 쓰는 물러섬 — 글자꼴만 본다
_SUFFIX_RULES = [
    (re.compile(r'(습니다|입니다|니다|세요|십시오|어요|아요|예요|죠|까요|나요)$'), 'EF'),
    (re.compile(r'(면서|지만|는데|니까|거나|더라도|도록|므로|다가|라면|다면|고자|려고|으며|으면|고|며|면)$'),
     'EC_CLOSE'),
    (re.compile(r'(아서|어서|여서|아야|어야|여야|아|어|여|게|지|고서)$'), 'EC_AUX'),
    (re.compile(r'(기|음|ㅁ)$'), 'ETN'),
    (re.compile(r'(적인|스러운|같은|다운|로운|하는|되는|있는|없는|했던|하던|되던|던|할|될)$'), 'ETM'),
    (re.compile(r'의$'), 'JKG'),
    (re.compile(r'(은|는|도|만|까지|부터|마다|조차|밖에|이나|라도)$'), 'JX'),
    (re.compile(r'(에서|에게|한테|으로|로|와|과|에|보다|처럼|같이)$'), 'JKB'),
    (re.compile(r'(을|를|이|가)$'), 'JKO'),
]

# Kiwi 의 연결어미(EC)는 '절을 닫는 것'과 '보조용언을 끌고 오는 것'을 안 가른다.
# 우리는 그 둘을 갈라야 해서 글자꼴로 한 번 더 본다 (rules.CLAUSE_CLOSING 참고).
_KIWI_EC = 'EC'


def strip_marks(word):
    """Word with punctuation removed -- what we look up."""
    return _NOISE.sub('', word)


def visible_len(text):
    """Length ignoring spaces and thin glyphs."""
    return len(_THIN.sub('', text))


class Tagger:
    """Tags for a word form. Create one and reuse it -- Kiwi is slow to start."""

    def __init__(self, table=None, use_kiwi=False, tags_path=None):
        self.table = table if table is not None else model.load(tags_path)
        self._kiwi = None
        self._want_kiwi = use_kiwi
        self._cache = {}

    @property
    def kiwi(self):
        if self._kiwi is None and self._want_kiwi:
            try:
                from kiwipiepy import Kiwi
                self._kiwi = Kiwi()
            except ImportError:
                self._want_kiwi = False      # 없으면 조용히 물러선다. 설치 안내는 README 에
        return self._kiwi

    def _kiwi_tags(self, form):
        k = self.kiwi
        if not k:
            return None
        try:
            tokens = k.tokenize(form)
        except Exception:
            return None
        if not tokens:
            return None
        return tokens[0].tag, tokens[-1].tag

    def _both(self, word):
        form = strip_marks(word)
        if not form:
            return None, None
        if form in self._cache:
            return self._cache[form]

        entry = self.table['words'].get(form)
        if entry:
            out = (entry[0], entry[1])
            self._cache[form] = out
            return out

        first = last = None
        table = self.table
        for k in range(min(5, len(form)), 1, -1):
            v = table['suffixes'].get(form[-k:])
            if v and v[1] >= 0.75 and v[2] >= 3:
                last = v[0]
                break
        for k in range(min(4, len(form)), 1, -1):
            v = table['prefixes'].get(form[:k])
            if v and v[1] >= 0.75 and v[2] >= 3:
                first = v[0]
                break

        if first is None or last is None:
            kt = self._kiwi_tags(form)
            if kt:
                first = first or kt[0]
                last = last or kt[1]

        if last is None:
            for pattern, tag in _SUFFIX_RULES:
                m = pattern.search(form)
                # 어간이 한 글자만 남아도 쓴다 — `띠며`·`닿아` 같은 짧은 용언꼴이 여기까지 온다
                if m and len(form) > (m.end() - m.start()):
                    last = tag
                    break

        out = (first, last)
        self._cache[form] = out
        return out

    def first_tag(self, word):
        return self._both(word)[0]

    def last_tag(self, word):
        return self._both(word)[1]

    def is_aux_verb(self, word):
        """``주는``/``않고``/``합니다`` -- a verb that cannot stand without the one before it.

        Matching by stem prefix alone is wrong: the aux-verb list contains ``가``,
        which made ``가격이`` ("the price") look like an auxiliary and blocked a
        break after a comma. The stem must be followed by **an ending**.
        """
        form = strip_marks(word)
        if form in _CONTRACTED_AUX:
            return True
        if self.first_tag(word) == 'VX':
            return True
        aux = self.table['aux_verbs']
        if form in aux:
            return True
        for stem in aux:
            if form.startswith(stem) and len(form) > len(stem) and _ENDING_TAIL.match(form[len(stem):]):
                return True
        return False

    def is_bound_noun(self, word):
        """``개를``/``것은``/``수``/``때는`` yes -- ``적용``/``개발`` no.

        A loose match here is destructive: treating ``적용`` as the bound noun
        ``적`` + something split compound nouns apart.
        """
        form = strip_marks(word)
        if self.first_tag(word) == 'NNB' and _PARTICLE_TAIL.match(form[1:] if len(form) > 1 else ''):
            return True
        for w in self.table['bound_nouns']:
            if form == w:
                return True
            if form.startswith(w) and form[len(w):] and _PARTICLE_TAIL.match(form[len(w):]):
                return True
        return False


# 어간 뒤에 붙는 어미 꼴 — 보조용언을 알아볼 때 쓴다
_ENDING_TAIL = re.compile(
    r'^(는|은|ㄴ|던|을|ㄹ|지|고|서|면|며|니|나|자|게|기|음|도록|려고'
    r'|았|었|겠|아|어|여|야|요|다|까|네|죠'
    r'|습니다|ㅂ니다|니다|세요|십시오|어요|아요|는다|ㄴ다|는데|지만'
    r'|으며|으면|으니|으나|으므로|으면서|으려고|으시|었으|겠으'
    r'|아서|어서|여서|아야|어야|여야|기는|지는)+$')

# 복수 `들` 을 빼먹어 `분들은` 이 의존명사로 안 잡혔다
_PARTICLE_TAIL = re.compile(
    r'^(들)?(이|가|은|는|을|를|에|의|도|만|과|와|로|으로|에서|에게|부터|까지|보다|처럼|이나|나'
    r'|이다|이라|이며|이고|입니다|이면|이지만|이므로|라도|조차|마저|밖에|마다|뿐|씩|째)?$')

# 줄어든 보조용언꼴 — 어간이 바뀌어서 어간+어미로는 못 맞춘다.
# `합니다` 는 `하` 로 시작하지 않는다(합≠하). 이것 때문에 `받아들여야 | 합니다` 가 갈렸다.
_CONTRACTED_AUX = {
    '합니다', '한다', '해', '해서', '해야', '했다', '했습니다', '하죠', '하자', '합시다',
    '됩니다', '된다', '돼', '돼서', '됐다', '됐습니다',
    '봅니다', '본다', '봐', '봐서', '봤다', '보죠',
    '줍니다', '준다', '줘', '줘서', '줬다', '주죠',
    '놓습니다', '놨다', '둡니다', '뒀다', '버립니다', '버렸다', '드립니다', '드렸다',
    '않습니다', '않는다', '않죠', '없습니다', '있습니다', '갑니다', '옵니다', '맙니다',
    '싶습니다', '싶다', '말아야', '마세요', '계십니다',
}
