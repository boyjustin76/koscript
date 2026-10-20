# koscript

**A toolkit for writing Korean video scripts.** Break lines where the grammar allows, not where
the character count lands. Check what you wrote against your sources. Fill the DOCX form your
producer sent you without breaking it.

한국어 영상 대본을 쓰는 연장통입니다. 아래 [한국어](#한국어) 참고.

> **Before you start:** `koscript.clause` needs the [NIKL corpus](https://corpus.korean.go.kr)
> — free, but you apply for it and a human approves, so **start that first**.
> [Kiwi](https://github.com/bab2min/Kiwi) is optional. **→ [docs/SETUP.md](docs/SETUP.md)**

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
| [**`clause`**](koscript/clause) | Break Korean text at clause and phrase boundaries. Graded — punctuation first, sentence endings next, particles only as a last resort. Never breaks before an auxiliary verb, a bound noun, or after `-의`. |
| [**`docx`**](koscript/docx) | Edit a `.docx` form without breaking it. Read a reviewer's **strikethrough and underline marks**. Diff two revisions paragraph by paragraph. Build OOXML that Word will actually open. |
| [**`premiere`**](koscript/premiere) | Build an FCP7 XML sequence Premiere will actually import -- including the `pathurl` encoding that silently breaks it. Read a `.prproj` without opening Premiere. |
| [**`pdfform`**](koscript/pdfform) | Read a **prompter script** out of a PDF as spoken sentences -- past the six ways `pdftotext` gets them wrong. Measure a PDF form you have to reproduce: page size, fonts, margins, highlighter colours. |

More to come -- copy-overlap checking.

## Install

```bash
git clone https://github.com/<you>/koscript && cd koscript && pip install -e .
# then get the corpus — docs/SETUP.md . `clause` needs it; `docx` does not.
pip install kiwipiepy           # optional, see "Does Kiwi help?" below
```

`pdfform` needs **poppler** on the machine (`pdftotext`, `pdftoppm`) — no Python package.
`clause`, `docx` and `premiere` need nothing but the standard library.

## Quick look

```python
from koscript.clause import split

split("이 선이 방향을 확정해 줄 때까지 기다렸다가 그다음에 움직이는 방식입니다.")
# ['이 선이 방향을 확정해 줄 때까지 기다렸다가',
#  '그다음에 움직이는 방식입니다.']
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
a person moved every break to where they wanted it. Score your own with:

```bash
python tools/score.py your_reference.txt
```

On that reference, re-splitting the same sentences:

| | |
|---|---|
| **precision** — breaks of mine the human also made | **0.909** |
| recall — human breaks I found | 0.606 |
| lines produced | 66 (the human made 99) |

**Precision is the number that matters.** Recall rewards breaking more often, which is the wrong
instinct: fewer, better-placed breaks win. The six remaining misses are all places where the
human broke after a comma inside a list and `clause` kept the list together.

The exact number moves a little with which corpus subset you build the table from --
88k word forms gave 0.909 here, 103k gave 0.910.

One reference is thin evidence. If you score it on your own material, please open an issue with
the number — that is the most useful contribution this project can get right now.

### Does Kiwi help?

Honest answer: **not yet, on the only reference we have.**

| | precision |
|---|---|
| corpus table + suffix rules (default) | **0.909** |
| corpus table + Kiwi + suffix rules | 0.894 |

Kiwi adds one break the human did not make. So it is **off by default** —
`Tagger(use_kiwi=True)` turns it on. It should earn its place on text full of words the corpus
never saw (loanwords, product names); that is untested. Measurements welcome.

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

> **먼저 받을 것:** [모두의 말뭉치](https://corpus.korean.go.kr) — 무료지만 **신청해서 승인**을
> 받아야 하니 **이것부터 넣어 두세요**. [Kiwi](https://github.com/bab2min/Kiwi) 는 선택입니다.
> **→ [docs/SETUP.md](docs/SETUP.md)**

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
- **`koscript.premiere`** — 프리미어가 **가져오기를 거부하는 여섯 가지**를 피한 FCP7 XML 짓기,
  프리미어 없이 `.prproj` 읽기
- **`koscript.pdfform`** — 촬영용 프롬프터 `.pdf` 에서 **낭독 문장** 뽑기
  (`pdftotext` 가 문장을 틀리는 여섯 가지), 맞춰야 할 양식 실측(쪽 크기·글꼴·여백·강조색)

## 얼마나 되나

사람이 손수 고친 기준판(실제 촬영 대본 99줄) 대비 **정밀 0.909** — 내가 끊은 자리 가운데
사람도 끊은 비율입니다. 재현 0.606, 줄 수 66(사람은 99).
**재현이 아니라 정밀을 봅니다** — 많이 끊을수록 재현은 오르는데 그건 틀린 방향입니다.
`python tools/score.py <기준판.txt>` 로 직접 재 보실 수 있습니다.

**Kiwi 는 이 기준판에서 도움이 안 됐습니다** — 0.909 → 0.894 로 오히려 한 자리를 더 끊습니다.
그래서 기본은 꺼 두었습니다(`Tagger(use_kiwi=True)` 로 켭니다). 말뭉치에 없는 말이 많은 글에서는
값을 할 것 같은데 아직 못 재 봤습니다. 기준판 하나로는 증거가 얇습니다.
