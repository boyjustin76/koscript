# `clause` — break Korean where the grammar allows

```python
from koscript.clause import split

split("이 선이 방향을 확정해 줄 때까지 기다렸다가 그다음에 움직이는 방식입니다.")
# ['이 선이 방향을 확정해 줄 때까지 기다렸다가', '그다음에 움직이는 방식입니다.']
```

**Needs the NIKL corpus table** — see [docs/SETUP.md](../../docs/SETUP.md). Without it the module
still runs, on suffix patterns alone, and places about one break in twelve badly.

## The rule

Every gap between two words gets a grade:

| grade | where | used |
|---|---|---|
| **1** | after punctuation | always |
| **2** | after a sentence ending, or a connective ending that **closes a clause** | always |
| **3** | after a particle or an adnominal ending | **only** to rescue a segment over `long_at` (40) |
| `None` | forbidden | never |

Only grades 1 and 2 are used normally. Grade 3 is a safety valve, not a target.

### Forbidden

Before an auxiliary verb · before a bound noun · before an adverb · before the copula ·
after the genitive `-의` · after a determiner · after a conjunctive `-와/과` ·
inside quotes or brackets · between the parts of a compound noun ·
before a verb that cannot stand alone (`불구하고`, `비해`, `통해`).

### Why `-게` and `-아/어/여` are not grade 2

They do not close a clause; they bind to the verb that follows.
`타이트하게 | 손절선을` and `지나치게 | 커진다면` read as broken. A human editor left both intact.

## Tuning

```python
split(text, long_at=40)              # the only length knob, and it is a last resort
split(text, tagger=Tagger(use_kiwi=True))
```

Reuse one `Tagger` across calls — it caches, and Kiwi is slow to construct.

## Swapping the analyzer

A tagger is anything with `first_tag`, `last_tag`, `is_aux_verb`, `is_bound_noun`:

```python
class MyTagger:
    def first_tag(self, word): ...      # 'NNG', 'VX', 'MAG', ...
    def last_tag(self, word): ...       # 'EF', 'EC', 'JKB', 'ETM', ...
    def is_aux_verb(self, word): ...
    def is_bound_noun(self, word): ...

split(text, tagger=MyTagger())
```

Tags follow the NIKL (세종) tagset, which Kiwi, MeCab-ko and KoNLPy all emit.

## Scoring your own

```bash
python tools/score.py your_reference.txt
```

One line of plain text per subtitle line. **Precision** — the share of *your* breaks the human
also made — is the number to watch. Recall goes up when you break more, which is the wrong way.

## Where it came from

Pulled out of a working pipeline for Korean YouTube long-form scripts, where character-count
splitting produced lines like `… 수치로 알려` / `주는 하나의 기준선일 뿐입니다` — a main verb cut
from its auxiliary. Every forbidden rule here exists because that specific break shipped once.
