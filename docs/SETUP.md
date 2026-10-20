# Setup — what to install before you start

`koscript` needs three things that **do not come with `pip install`**:

1. **Kiwi** — a Korean morphological analyzer. One `pip` line. 2 minutes.
2. **NIKL corpus (모두의 말뭉치)** — a Korean corpus you must **apply for**. Free, but a human
   approves it. A few days.
3. **poppler** — command-line PDF tools, needed by `pdfform`. One install line. 2 minutes.

This is normal for language tooling — spaCy makes you download a model, NLTK makes you download
`punkt`, MeCab makes you build a dictionary. The difference here is that the corpus needs an
application, so **start step 2 first and do everything else while you wait.**

한국어 안내는 아래 [한국어](#한국어) 절에 같은 내용이 있습니다.

---

## 1. Kiwi (2 minutes)

```bash
pip install kiwipiepy
```

That's it. Verify:

```python
from kiwipiepy import Kiwi
print(Kiwi().tokenize("선이 방향을 확정해 줄 때까지 기다립니다."))
```

Kiwi gives us the part-of-speech tag of every word. `koscript` decides **where a line may break**
from those tags — not from character counts.

> Kiwi is LGPL-3.0. `koscript` only *calls* it (it is a separate pip package, not bundled), so
> `koscript` stays MIT. If LGPL is a problem for you, see [Other analyzers](#other-analyzers).

## 2. NIKL corpus 모두의 말뭉치 (apply first, it takes days)

### What it is

**모두의 말뭉치** ("Everyone's Corpus") is a large collection of Korean text published by the
**National Institute of Korean Language (국립국어원, NIKL)** — the Korean government's language
institute. Think of it as Korea's official reference text collection.

We use one part of it: **형태 분석 말뭉치 (NIKL_MP)** — Korean sentences where every word is
already tagged with its part of speech by linguists.

### Why `koscript` needs it

Kiwi tells you what *a* word is. The corpus tells you **what real people actually write.**

Example — where can `선이 방향을 확정해 줄 때까지` break?

| | |
|---|---|
| Kiwi alone | `줄` could be a noun ("line"), or the auxiliary verb in `해 주다`. Ambiguous. |
| With the corpus | `확정해 줄` appears as one chunk thousands of times. **Never break there.** |

`koscript` builds a lookup table from the corpus once (~90k word forms, ~1 MB) and uses it to
resolve exactly these cases. Without it, line breaks land mid-phrase on about 1 in 12 lines.

### How to get it

1. Go to **<https://corpus.korean.go.kr>** (모두의 말뭉치).
2. **Sign up.** A Korean phone number or an email address works; you do not need to live in Korea.
3. Menu **말뭉치 내려받기** (Download corpora). Find **형태 분석 말뭉치** (Morpheme-analyzed corpus).
4. Click **신청하기** (Apply). You fill in:
   - **사용 목적** (purpose) — write plainly what you will do with it.
     e.g. *"오픈소스 자막 줄바꿈 도구의 어절 사전 구축"* / *"Building a word-form table for an
     open-source subtitle line-breaking tool."*
   - **이용 기간** (period), **소속** (affiliation; a person is fine)
5. **Agree to the terms** (이용 약관). Read the redistribution clause — in short:
   **you may use the corpus, you may not redistribute it or files derived from it.**
   That is why this repository ships the *builder*, not the table.
6. Wait. Approval is a person reading your application — usually **1–5 business days**.
7. When approved, download. You get `.zip` files — the one we want contains JSON files
   under a folder like `NXMP*` or `국립국어원 형태 분석 말뭉치*`.

> **Applying is in Korean.** If you do not read Korean, the form is short — browser translation
> handles it. The fields above are all of them.

### Where to put it

Unzip anywhere, then build the table:

```bash
python -m koscript.clause.build_tags  path/to/unzipped/corpus  koscript/clause/data/ko_tags.json.gz
```

Takes a few minutes. You only do it once.

Then point `koscript` at it — either place it at the default path above, or set:

```bash
export KOSCRIPT_TAGS=/path/to/ko_tags.json.gz
```

### Checking it worked

```python
from koscript.clause import model
print(model.info())      # {'word_forms': 88457, 'endings': 17207, 'source': '...'}
```

If you see `word_forms: 0`, the table was not found — `koscript` will tell you which paths it
looked at.

---

## Other analyzers

Kiwi is the default because it installs with one `pip` line and needs no system packages.
If you already run **MeCab-ko** or **KoNLPy**, you can plug it in — see
[`koscript/clause/README.md`](../koscript/clause/README.md#swapping-the-analyzer).

## 3. poppler — needed by `pdfform`, and by `docx.render`

```
Windows:  winget install oschwartz10612.Poppler
macOS:    brew install poppler
Debian:   apt install poppler-utils
```

`koscript.pdfform` runs `pdftotext`, `pdftoppm`, `pdffonts` and `pdfinfo`. There is no
Python package to install — they are command-line programs.

**On Windows the installer does not put them on `PATH`.** They land in a versioned
folder under `%LOCALAPPDATA%\Microsoft\WinGet\Packages`, which `koscript` searches, so
it usually just works. If it does not, set `KOSCRIPT_POPPLER` to the folder holding the
binaries.

> **Watch out: `pdftotext` on `PATH` may not be poppler.** Xpdf ships a program by the
> same name, and Git for Windows installs one in `/mingw64/bin`. `koscript` identifies
> candidates by their `-v` banner and prefers a real poppler, so you do not have to care
> — but if something reads oddly, `poppler.banner('pdftotext')` tells you which one you
> got.

### Also for `docx.render` only

`koscript.docx.render` turns a `.docx` into page images so you can look at it. On top of
poppler it needs **LibreOffice** — <https://www.libreoffice.org/download/>. Set
`SOFFICE` if it is somewhere unusual.

Everything else in `koscript` is standard library only.

---

# 한국어

## 1. Kiwi — 2분

```bash
pip install kiwipiepy
```

끝입니다. Kiwi 는 낱말마다 품사를 알려 줍니다. `koscript` 는 **글자 수가 아니라 그 품사로**
줄을 어디서 끊을지 정합니다.

## 2. 모두의 말뭉치 — 신청부터 하세요, 며칠 걸립니다

### 무엇인가

**국립국어원**이 펴낸 한국어 말뭉치 모음입니다. 그중 **형태 분석 말뭉치(NIKL_MP)** 를 씁니다 —
낱말마다 품사가 붙어 있는 자료입니다.

### 왜 필요한가

Kiwi 는 *한* 낱말이 무엇인지 알려 주고, 말뭉치는 **사람들이 실제로 어떻게 쓰는지**를 알려 줍니다.
`확정해 줄` 의 `줄` 이 명사인지 보조용언인지는 Kiwi 만으로 못 가립니다. 말뭉치에서 `확정해 줄` 이
한 덩어리로 수천 번 나오는 걸 보고 **거기서 끊지 않기로** 정합니다.
말뭉치 없이 돌리면 열두 줄에 한 줄꼴로 말 중간에서 끊깁니다.

### 받는 법

1. <https://corpus.korean.go.kr> 에서 **회원 가입**
2. **말뭉치 내려받기** → **형태 분석 말뭉치** → **신청하기**
3. **사용 목적**을 적습니다. 꾸밀 것 없이 사실대로 —
   *"오픈소스 자막 줄바꿈 도구의 어절 사전 구축"*
4. **이용 약관**에 동의합니다. 요지는 **쓰는 건 되고, 자료나 그 파생물을 다시 배포하는 건 안 된다**는
   것입니다. 이 저장소가 표 파일 대신 **만드는 코드**만 올려 둔 이유입니다
5. 기다립니다. 사람이 읽고 승인합니다 — 보통 **영업일 1~5일**
6. 승인되면 내려받아 압축을 풉니다

### 두는 곳

```bash
python -m koscript.clause.build_tags  <압축 푼 폴더>  koscript/clause/data/ko_tags.json.gz
```

한 번만 돌리면 됩니다. 다른 자리에 두려면 `KOSCRIPT_TAGS` 환경변수로 경로를 주세요.

### 됐는지 보기

```python
from koscript.clause import model
print(model.info())
```

`word_forms: 0` 이면 표를 못 찾은 것입니다 — 어느 경로를 봤는지 같이 알려 줍니다.

## 3. poppler — `pdfform` 이 씁니다, 2분

```
윈도우:  winget install oschwartz10612.Poppler
맥:     brew install poppler
우분투:  apt install poppler-utils
```

`koscript.pdfform` 은 `pdftotext`·`pdftoppm`·`pdffonts`·`pdfinfo` 를 부릅니다.
파이썬 꾸러미가 아니라 **명령줄 프로그램**이라 `pip` 로는 안 깔립니다.

**윈도우는 설치해도 `PATH` 에 안 잡힙니다.** `%LOCALAPPDATA%` 아래 winget 폴더(판번호가
붙습니다)에 들어가는데, `koscript` 가 거기를 찾아보니 보통은 그냥 됩니다.
못 찾으면 `KOSCRIPT_POPPLER` 환경변수로 그 `bin` 폴더를 알려 주세요.

> **주의 — `PATH` 의 `pdftotext` 가 poppler 가 아닐 수 있습니다.** Xpdf 가 같은 이름의
> 프로그램을 내놓고, Git for Windows 는 `/mingw64/bin` 에 그걸 깔아 둡니다. 바꿔 써도 되는
> 물건이 아닙니다 — `-layout` 결과의 들여쓰기가 달라지고, **`-enc UTF-8` 없이는 한글을 아무
> 말 없이 다 버립니다**(오류도 없이 문장부호만 남습니다).
> `koscript` 가 `-v` 머리글로 가려서 진짜 poppler 를 고르니 신경 쓸 일은 없지만, 뭔가
> 이상하면 `poppler.banner('pdftotext')` 로 어느 쪽이 잡혔는지 보세요.

## 4. `docx.render` 만 더 필요한 것

`.docx` 를 쪽 그림으로 바꿔 눈으로 보려면 poppler 말고 **LibreOffice** 가 더 있어야 합니다
(<https://www.libreoffice.org/download/>). 엉뚱한 자리에 깔려 있으면 `SOFFICE` 로 알려 주세요.

나머지는 전부 파이썬 표준 라이브러리만 씁니다.
