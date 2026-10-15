# koscript

**A toolkit for writing Korean video scripts.** Break lines where the grammar allows, not where
the character count lands. Check what you wrote against your sources. Fill the DOCX form your
producer sent you without breaking it.

한국어 영상 대본을 쓰는 연장통입니다. 아래 [한국어](#한국어) 참고.

> **Before you start:** `koscript` needs [Kiwi](https://github.com/bab2min/Kiwi) (one `pip` line)
> and the [NIKL corpus](https://corpus.korean.go.kr) (free, but you apply for it and a human
> approves — start that first). **→ [docs/SETUP.md](docs/SETUP.md)**

---

## The problem

Every subtitle tool breaks Korean lines by counting characters. Korean does not survive that.

```
어떻게 끊어야 하나  →  글자 수로 (what tools do)   문법으로 (koscript)
────────────────────────────────────────────────────────────────────
선이 방향을 확정해      선이 방향을 확정해 줄      선이 방향을 확정해 줄
줄 때까지 기다렸다가    때까지 기다렸다가 그       때까지 기다렸다가
그 방향으로만           방향으로만 들어가는        그 방향으로만 들어가는
들어가는 매매법         매매법                     매매법
                        ↑ `확정해 줄` 이 쪼개짐    ↑ 구 단위로 끊김
```

This is not a solved problem. [libass #694](https://github.com/libass/libass/issues/694) notes
that for Korean, ICU and Budou both fall back to *"break on spaces."* Subtitle editors carry open
issues about it. At least one tool asks an LLM to do it.

`koscript` does it deterministically, from morphology tags, measured against a human-edited
reference.

## What is in here

| | |
|---|---|
| **`koscript.clause`** | Break Korean text at clause and phrase boundaries. Graded — punctuation first, sentence endings next, particles only as a last resort. Never breaks before an auxiliary verb, a bound noun, or after `-의`. |
| **`koscript.docx`** | Edit a `.docx` form without breaking it. Read a reviewer's **strikethrough and underline marks**. Diff two revisions paragraph by paragraph. Build OOXML that Word will actually open. |

More to come — prompter PDF reading, copy-overlap checking, Premiere XML.

## Install

```bash
pip install kiwipiepy          # required
git clone https://github.com/<you>/koscript && cd koscript && pip install -e .
# then get the corpus — docs/SETUP.md
```

## Quick look

```python
from koscript.clause import split

split("선이 방향을 확정해 줄 때까지 기다렸다가 그 방향으로만 들어가는 매매법입니다.")
# ['선이 방향을 확정해 줄 때까지 기다렸다가',
#  '그 방향으로만 들어가는 매매법입니다.']
```

```python
from koscript.docx import pack, read, edit

doc  = pack.unpack("form.docx", "work")
body = pack.read_body(doc)

for i, marked in read.read_marks(body):           # what the reviewer changed
    print(i, marked)
# 12 그래서 다음에는 [-무너지는 날도 있죠.-][_무너지죠._]

body = edit.replace_once(body, "무너지는 날도 있죠.", "무너지죠.")   # raises if not exactly 1
pack.write_body(doc, body); pack.repack(doc, "edited.docx")
```

## How good is it

`clause` is tuned against a reference edited by hand — 99 lines of a real shooting script, where
a person moved every break to where they wanted it.

| | character-count | koscript |
|---|---|---|
| **precision** (breaks a human accepts) | 0.76 | **0.93** |
| lines produced | 174 | 112 |

Precision is the number that matters. Recall rewards breaking more often, which is the wrong
instinct — the fewer, better-placed breaks win.

## Status

Early. `clause` and `docx` work and are tested; the rest is being extracted from a working
production pipeline. Interfaces may move before `1.0`.

## License

MIT — see [LICENSE](LICENSE). Kiwi (LGPL-3.0) and the NIKL corpus are **separate** dependencies
you install yourself; neither is bundled here, and the corpus terms forbid redistributing it or
anything derived from it.

---

# 한국어

**한국어 영상 대본을 쓰는 연장통.** 자막 줄을 글자 수가 아니라 **문법으로** 끊고, 쓴 글을
출처에 맞대 보고, 받은 워드 양식을 안 깨뜨리고 채웁니다.

> **먼저 받을 것:** [Kiwi](https://github.com/bab2min/Kiwi) (`pip` 한 줄) 와
> [모두의 말뭉치](https://corpus.korean.go.kr) (무료지만 **신청해서 승인**을 받아야 합니다 —
> 이것부터 넣어 두세요). **→ [docs/SETUP.md](docs/SETUP.md)**

## 왜 만들었나

자막 도구는 전부 글자 수로 줄을 끊습니다. 한국어는 그러면 `확정해 / 줄` 처럼 말 중간이 갈립니다.
libass 이슈 #694 를 보면 한국어는 ICU·Budou 모두 **"띄어쓰기에서만 자른다"** 가 권고안이고,
자막 편집기들에는 이 불만 이슈가 열려 있습니다. 어떤 도구는 LLM 에 물어서 해결합니다.

`koscript` 는 형태소 태그로 **규칙에 따라** 끊고, 사람이 손수 고친 기준판에 맞대어 값을 잽니다.

## 들어 있는 것

- **`koscript.clause`** — 구·절 단위로 끊기. 등급제 — 구두점 먼저, 종결·연결어미 다음,
  조사는 마지막 수단. 보조용언·의존명사 앞, `-의` 뒤에서는 끊지 않습니다
- **`koscript.docx`** — 워드 양식 안 깨고 고치기, **취소선·밑줄 검토 표시 읽기**,
  두 판 문단 전수 대조, 워드가 여는 OOXML 짓기

## 얼마나 되나

사람이 손수 고친 기준판(실제 촬영 대본 99줄) 대비 **정밀 0.76 → 0.93**, 줄 수 174 → 112.
재현이 아니라 정밀을 봅니다 — 많이 끊을수록 재현은 오르는데, 그건 틀린 방향입니다.
