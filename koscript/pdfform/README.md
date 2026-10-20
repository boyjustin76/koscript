# `pdfform` — read a prompter script out of a PDF, and measure a form you have to match

Needs [poppler](https://poppler.freedesktop.org) on the machine. No Python packages.

```python
from koscript.pdfform import prompter

sections, unresolved = prompter.read('shooting_script.pdf')
sections[0]
# {'section': 'INTRO', 'title': '첫 구간의 제목',
#  'sentences': ['안녕하세요.', "오늘은 선을 두 개 겹쳐 쓰는 '더블 보조선' 방식을 봅니다.", ...]}
```

Input: a PDF written to be read off a prompter while filming — one spoken line per
paragraph, blank lines between, stage directions in brackets, and blocks the presenter
is not meant to read. Output: the spoken sentences, per section, ready to line up
against a transcript or cut into subtitles.

Run it on the worked example first: [`examples/pdfform`](../../examples/pdfform).

## Six ways `pdftotext` gets the sentences wrong

`pdftotext` gives you the characters. The sentences are the hard part, and each of these
was found by a wrong subtitle shipping.

| | |
|---|---|
| **1. One blank line is not a paragraph break** | The prompter put it there to space the lines out. Measured over one 10-page script: **97** single blanks (line wrap) against **26** doubles (real break). Treat one as a break and cues get cut mid-word — `… 겹쳐 사용하는 '더블` / `볼린저 밴드' 매매법을`. |
| **2. A page turn lands mid-sentence** | It brings a running header and ~4 blank lines. Count those as a break and one sentence becomes two. The form feed is the real signal, so a script with no header is handled too. |
| **3. A justified line wraps inside a word** | `절대` / `적인 기준으로` rejoined with a space gives `절대 적인`, which is not a word. **No rule decides this** — `절대`+`적인` joins, `청산하여`+`수익을` does not. Twelve of these reached the subtitles once. |
| **4. Stage directions hide inside a spoken line** | `맞습니다. (차트를 보며 횡보장 매매 설명)` — you cannot filter them by line. Keyed on the verb, because `(가짜 신호)` *is* read aloud. |
| **5. Not every sentence ends with a period** | Writers drop it at a line end. So a line ending on a sentence ending is also a break — but **only where the PDF broke the line**, never inside one. |
| **6. The PDF splits a number from its particle** | `표준편차 2 의`, `20 에서`. Left alone it reaches the subtitle as `2 의`, and clause splitting mis-reads `20 | 에서`. |

### Trap 3 is not solved, it is reported

The second return value holds the word pairs where a justified wrap could not be
decided. They are handed back rather than guessed, because joining wrongly invents a
word that does not exist in the language.

Give it a transcript and the decision comes from how the sentence was actually spoken:

```python
sections, unresolved = prompter.read('script.pdf', spoken='cam_transcript.json')
```

It counts both spellings in the transcript and takes the more frequent. On the script
this was built for, that settled 11 of 12; the last one a person had to look at.

## Nothing here is tied to one template

The running header is **detected, not configured** — a line that repeats across pages
*and* sits at the top or bottom of every page it appears on. The position test is what
stops a sentence that happens to repeat from being deleted from the script.

Everything else is a field on `Layout`:

```python
mine = prompter.Layout(heading=re.compile(r'^PART (\d+)\.\s*(\S.*)$'),
                       continuation_indent=4)
sections, _ = prompter.read('other_template.pdf', layout=mine)
```

`continuation_indent` is the one number worth re-measuring on a new template: how far a
justified wrap is indented relative to the paragraph it continues.

## What it will not do

- **One column only.** `pdftotext -layout` writes two table cells that sit side by side
  onto the same line, so a table-shaped document read as a prompter script produces
  sentences welded out of two different cells — quietly, and they look almost plausible.
  Check first: `prompter.looks_single_column(poppler.text(path))`.
- **No text layer, no sentences.** A scanned or image-only PDF needs OCR first; nothing
  here does that.
- **Trap 3 stays open without a transcript.** It is reported, not guessed.

## Measuring a form you have to reproduce

Someone sends a template as a PDF, with no source file, and asks for the next one in the
same shape. Guessing gets you a document that looks almost right, which is worse than
one that looks wrong.

```python
from koscript.pdfform import probe

form = probe.form('template.pdf')
form['size_pt']       # (612.0, 792.0)  -> US Letter, not A4
form['margins_pt']    # {'left': 72.4, 'top': 71.9, ...}  -> one inch
form['fonts'][0]      # {'name': 'ABCDEE+MalgunGothic', 'type': 'TrueType', ...}
form['fills'][0]      # {'rgb': '#FFFF00', 'pixels': 9183, 'box': (left, top, right, bottom)}
```

**Measure the pixels, not the settings.** A settings dialog tells you the value someone
typed; the rendered page tells you what a reader sees. The two differ often enough to
matter — a line style set to `0` turned out to render as dots, not the solid line the
number implied.

`fills` is how you recover which highlighter colours a reviewer used, and where. Greys
are dropped, because black text antialiases through grey and so does a hairline rule; a
pixel count cut-off separates a pen stroke from a letter's fringe.

`pdftoppm` writes a PPM — a short header and then raw RGB — so reading a pixel needs no
imaging library.

## Three things about poppler that cost an afternoon

- **The binaries are not on `PATH` on Windows.** `winget install
  oschwartz10612.Poppler` puts them in a versioned folder under
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages`. Set `KOSCRIPT_POPPLER` to the `bin`
  folder, or let `poppler.tool()` find it.
- **The `pdftotext` on `PATH` may not be poppler.** Xpdf ships a program by the same
  name, and Git for Windows installs one in `/mingw64/bin`. It is not a drop-in: its
  `-layout` moves the indents, and indent is how trap 3 is detected. So candidates are
  identified by their `-v` banner and a real poppler wins whatever the `PATH` order says
  — `poppler.banner('pdftotext')` tells you which one you got.
- **Xpdf's `pdftotext` silently drops every non-ASCII character** without `-enc UTF-8`.
  No warning, exit status 0: a Korean script comes out as the punctuation between the
  words. The flag is always passed; poppler ignores it.

And one about `pdftoppm`: **no output name at all** is how it writes to stdout. Passing
`-`, which is stdout for every other poppler tool, makes it write a file called
`--1.ppm` into the working directory and print nothing — exit status 0.
