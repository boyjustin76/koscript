# -*- coding: utf-8 -*-
"""Read a prompter script PDF back into sections and read-aloud sentences.

A prompter script is a document written to be *read off a screen while filming*:
one spoken line per paragraph, a blank line between them, stage directions in
brackets, and blocks the presenter is not supposed to read at all. It comes back
to you as a PDF, and you need the spoken sentences out of it -- to line them up
against a transcript, to find takes, to cut subtitles.

``pdftotext`` gives you the characters. Getting the *sentences* is where it goes
wrong, and every one of these was found by a wrong subtitle shipping:

**1. One blank line is not the end of a paragraph.** The prompter put it there to
space the lines out. Measured on a 10-page script: 97 single blanks (line wrap),
26 doubles (paragraph break), 25 none (around page furniture). Treat a single
blank as a paragraph break and you get subtitle cues cut mid-word --
``... 겹쳐 사용하는 '더블`` / ``볼린저 밴드' 매매법을``.

**2. A page turn lands in the middle of a sentence.** It brings a running header
and about four blank lines with it. Count those as a paragraph break and one
sentence becomes two.

**3. A justified paragraph wraps inside a word.** ``절대`` / ``적인 기준으로``
rejoined with a space gives ``절대 적인``, which is not a word. Twelve of these
reached the subtitles once. An indented continuation line is the candidate, but
**whether to join or to space cannot be decided by rule** -- ``절대``+``적인``
joins, ``청산하여``+``수익을`` does not. Pass a transcript and the decision comes
from how the sentence was actually spoken; without one, these come back to you in
the second return value instead of being guessed.

**4. Stage directions hide inside a spoken line** -- ``맞습니다. (차트를 보며
횡보장 매매 설명)``. You cannot filter them by line.

**5. Not every sentence ends with a period.** Writers drop it at a line end. Split
on periods only and two sentences arrive as one long cue, so a line that ends on a
sentence ending is also a break -- but only where the PDF itself broke the line,
never inside one.

**6. The PDF splits a number from the particle that follows it** -- ``표준편차 2
의``, ``20 에서``. Left alone it reaches the subtitle as ``2 의``, and clause
splitting mis-reads ``20 | 에서``.

Everything specific to one producer's template -- what the running header says,
which bracketed label means "do not read" -- is in :class:`Layout` or detected
from the document. Nothing is hard-coded here.

    sections, unresolved = prompter.read('script.pdf')
    sections[0]
    # {'section': 'INTRO', 'title': '...', 'sentences': ['...', '...']}
"""
import io
import json
import re

from . import poppler

HEADING = re.compile(r'^(INTRO|OUTRO)\.?\s*(.*)$|^(\d+)\.\s*(\S.*)$')
#: A line that is nothing but a bracketed label: ``[chart runs, not read aloud]``.
SKIP_BLOCK = re.compile(r'^\[[^\]]*\]$')
#: A parenthetical that is a direction to the presenter, not words to say.
#: Keyed on the verb, because ``(가짜 신호)`` and ``(1)`` *are* read aloud.
ASIDE = re.compile(r'\s*\([^()]*(설명|언급|보여주며|보여줍니다|표시합니다|진행)[^()]*\)')
BULLET = re.compile(r'^([•·]|\(\d+\)|\d+\))\s*')
ENDING = re.compile(r'(니다|니까|세요|십시오|죠|예요|어요|아요|한다|된다|이다)$')
PARTICLE_AFTER_NUMBER = re.compile(
    r'(?<=\d)\s+(의|이|가|은|는|을|를|에|에서|로|으로|과|와|도|만|까지|부터'
    r'|일|개|가지|번|차|초|분|배|회|명|원|년|월|주|배수|퍼센트|%)(?=\s|[,.)\]]|$)')

#: Marks where the PDF itself broke the line. Sentences may only be cut here --
#: anywhere else is the middle of a line the writer wrote as one piece.
WRAP = '\x00'


class Layout(object):
    """What one producer's template looks like. Everything has a default.

    ``continuation_indent`` is the one number worth re-measuring: how far a
    justified wrap is indented relative to the paragraph it continues.
    """

    def __init__(self, heading=HEADING, skip_block=SKIP_BLOCK, aside=ASIDE,
                 bullet=BULLET, ending=ENDING, glue=PARTICLE_AFTER_NUMBER,
                 drop=None, continuation_indent=3):
        self.heading = heading
        self.skip_block = skip_block
        self.aside = aside
        self.bullet = bullet
        self.ending = ending
        self.glue = glue
        #: Extra lines to treat as page furniture, on top of the detected ones.
        self.drop = drop
        self.continuation_indent = continuation_indent


DEFAULT = Layout()


def page_furniture(text, min_pages=2, edge=3):
    """Lines that are the running header or footer, found rather than configured.

    A line counts as furniture when it appears on at least ``min_pages`` pages
    **and** sits within ``edge`` lines of the top or bottom of every page it
    appears on. The position test is what keeps a sentence that happens to be
    repeated from being deleted from the script.
    """
    seen = {}
    for page in text.split('\f'):
        got = [l.strip() for l in page.split('\n') if l.strip()]
        if not got:
            continue
        rim = set(got[:edge]) | set(got[-edge:])
        for line in set(got):
            count, at_rim = seen.get(line, (0, True))
            seen[line] = (count + 1, at_rim and line in rim)
    return set(l for l, (count, at_rim) in seen.items() if count >= min_pages and at_rim)


#: Two columns on one line leave a wide gap in the middle of it.
COLUMN_GAP = re.compile(r'\S {4,}\S')


def looks_single_column(text, tolerance=0.03):
    """Is this a one-column document? **Check before trusting the sentences.**

    ``pdftotext -layout`` writes two table cells that sit side by side onto the
    same line, so a table-shaped document read as a prompter script produces
    sentences welded together out of two different cells -- quietly, and they
    look almost plausible. A wide gap inside a line is the tell.

    Measured on three real documents: two prompter scripts gave 0.0% and 0.9% of
    lines with a wide internal gap, a table-shaped one 6.1%. That is thin
    evidence for the 3% default, hence the parameter.
    """
    got = [l.strip() for l in text.split('\n') if l.strip()]
    if not got:
        return True
    wide = sum(1 for l in got if COLUMN_GAP.search(l))
    return wide <= tolerance * len(got)


def heading_of(line, layout=DEFAULT):
    """``(number_or_name, title)`` if the line opens a section, else ``None``."""
    m = layout.heading.match(line)
    if not m:
        return None
    if m.group(1):
        return m.group(1), (m.group(2) or '').strip()
    return m.group(3), (m.group(4) or '').strip()


def spoken_words(path):
    """A transcript as one spacing-preserved string, for :func:`joins`.

    Accepts a list of segments or ``{"segments": [...]}`` / ``{"words": [...]}``,
    with the text under ``text`` or ``word`` -- which covers what Whisper and
    most STT tools write out.
    """
    data = json.load(io.open(path, encoding='utf-8'))
    parts = data if isinstance(data, list) else data.get('segments', data.get('words', []))
    return re.sub(r'\s+', ' ', ' '.join(p.get('text', p.get('word', '')) for p in parts))


def joins(left, right, spoken=None):
    """Was the justified wrap inside a word? ``True`` join, ``False`` space, ``None`` unknown.

    No rule decides this (trap 3). With a transcript we count both spellings in
    what was actually said and take the more frequent. Without one the answer is
    ``None`` -- the caller is told, rather than being handed a guess, because
    joining wrongly invents a word that does not exist.
    """
    tail = (left.split() or [''])[-1]
    head = (right.split() or [''])[0]
    if not re.search(r'[가-힣\d]$', tail) or not re.match(r'[가-힣\d]', head):
        return False
    if re.search(r'[.?!,:;)\]]$', tail):
        return False
    if spoken:
        together, apart = spoken.count(tail + head), spoken.count(tail + ' ' + head)
        if together or apart:
            return together > apart
    return None


def split_sentences(paragraph, layout=DEFAULT):
    """Cut a paragraph into sentences, **only at line breaks the PDF made**.

    Periods first; then any line that ends on a sentence ending, because writers
    drop the final period (trap 5).
    """
    out = []
    for chunk in re.split(r'(?<=[.?!])[%s\s]+' % WRAP, paragraph.strip()):
        held = ''
        for piece in chunk.split(WRAP):
            held = (held + ' ' + piece).strip() if held else piece
            if layout.ending.search(held.rstrip()):
                out.append(held)
                held = ''
        if held:
            out.append(held)
    return [layout.glue.sub(r'\1', re.sub(r'\s+', ' ', s)).strip()
            for s in out if len(s.strip()) >= 2]


def parse(text, layout=DEFAULT, spoken=None, furniture=None):
    """``(sections, unresolved)`` from ``pdftotext -layout`` output.

    ``sections`` is ``[{'section', 'title', 'sentences'}]``; ``unresolved`` is the
    ``(left, right)`` word pairs where a justified wrap could not be decided
    (trap 3) and a person has to look.

    Anything before the first section heading -- a cover page, a run-time note --
    is dropped: there is nothing to attach it to.
    """
    if furniture is None:
        furniture = page_furniture(text)
    sections, now, held, skipping, turned, blanks, unresolved = [], None, [], False, False, 0, []

    def close():
        """Join the held lines into one paragraph, then cut it into sentences."""
        if not held:
            return
        got = held[:]
        held[:] = []
        para = got[0][1]
        for indent, line in got[1:]:
            join = False
            if indent >= layout.continuation_indent and not layout.bullet.match(line):
                verdict = joins(para, line, spoken)
                if verdict is None:
                    unresolved.append(((para.split() or [''])[-1], (line.split() or [''])[0]))
                join = bool(verdict)
            para += ('' if join else WRAP) + line
        para = layout.bullet.sub('', para).strip()      # the bullet glyph is not read aloud
        if para and now is not None:
            now['sentences'] += split_sentences(para, layout)

    for raw in text.split('\n'):
        page_break = '\f' in raw
        raw = raw.replace('\f', '')
        line = raw.strip()
        if not line:
            blanks += 1
            # Blank lines belonging to a page turn do not end a paragraph (trap 2)
            if blanks >= 2 and not turned:
                close()
                skipping = False
            continue
        was_blank, blanks = blanks, 0
        indent = len(raw) - len(raw.lstrip())
        if line in furniture or (layout.drop and layout.drop.match(line)):
            turned, skipping = True, False          # the paragraph continues across it
            continue
        line = layout.aside.sub('', line).strip()   # directions inside a spoken line (trap 4)
        if not line:
            continue
        head = heading_of(line, layout)
        if head:
            close()
            now = {'section': head[0], 'title': head[1], 'sentences': []}
            sections.append(now)
            skipping, turned = False, False
            continue
        if layout.skip_block.match(line):
            close()
            skipping, turned = True, False
            continue
        # A form feed sits at the end of the last line of the page when there is no
        # running header, so the turn applies to the gap *after* this line.
        after_turn, turned = turned, page_break
        if skipping:
            continue
        last_indent = held[-1][0] if held else 0
        if layout.bullet.match(line) and indent < layout.continuation_indent:
            close()                                 # each bullet is its own paragraph
        elif indent == 0 and last_indent >= 2:
            close()                                 # back to body text from a bullet block
        elif was_blank >= 2 and not after_turn:
            close()
        held.append((indent, line))
    close()
    return sections, unresolved


def read(path, spoken=None, layout=DEFAULT):
    """:func:`parse` the text of a PDF. ``spoken`` is a transcript ``.json`` path, or the words themselves."""
    if spoken and spoken.lower().endswith('.json'):
        spoken = spoken_words(spoken)
    return parse(poppler.text(path), layout, spoken)


def minutes(sections, chars_per_second=6.8):
    """Rough read-aloud length per section, in minutes.

    6.8 characters a second is measured from 13 finished Korean videos. It is a
    median, not a law -- use it to spot a section that is twice as long as it
    should be, not to promise a running time.
    """
    return [(s['section'], sum(len(t) for t in s['sentences']) / chars_per_second / 60.0)
            for s in sections]
