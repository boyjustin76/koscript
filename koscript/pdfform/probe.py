# -*- coding: utf-8 -*-
"""Measure a PDF you have to reproduce: page size, fonts, margins, highlight colours.

Someone sends you a template as a PDF -- no source file -- and asks for the next
one in the same form. Guessing the page size, the margins and the highlighter
colours gets you a document that looks almost right, which is worse than one that
looks wrong. Measure them instead.

**Measure the pixels, not the settings.** A settings dialog tells you the value
that was typed in; a rendered page tells you what the reader actually sees. The
two differ often enough to matter -- a line style set to "0" rendered as dots,
not as the solid line the number implied.

    form = probe.form('template.pdf')
    form['size_pt']       # (612.0, 792.0)  -> US Letter
    form['margins_pt']    # {'left': 72.4, 'top': 71.9, ...}  -> one inch
    form['fonts'][0]      # {'name': 'ABCDEE+MalgunGothic', 'type': 'TrueType', ...}
    form['fills'][0]      # {'rgb': '#FFFF00', 'pixels': 9183, 'box': (l, t, r, b)}

The only dependency is poppler. ``pdftoppm`` writes a PPM, which is a header and
then raw RGB bytes, so no imaging library is needed to read a pixel.
"""
from . import poppler


class Raster(object):
    """One rendered page: ``width`` x ``height`` pixels of RGB at ``dpi``."""

    def __init__(self, width, height, data, dpi=72):
        self.width = width
        self.height = height
        self.data = data
        self.dpi = dpi

    def pixel(self, x, y):
        i = (y * self.width + x) * 3
        return tuple(bytearray(self.data[i:i + 3]))

    def pt(self, px):
        """Pixels to points, at this render's resolution."""
        return px * 72.0 / self.dpi

    def ink_box(self, white=245):
        """``(left, top, right, bottom)`` in pixels of everything that is not page white.

        ``None`` for a blank page. This is how you measure margins without the
        source file -- but note it finds the *ink*, so a page whose header rule
        runs into the margin measures a smaller margin than the one that was set.
        """
        w, h, data = self.width, self.height, self.data
        left, top, right, bottom = w, h, -1, -1
        for y in range(h):
            row = data[y * w * 3:(y + 1) * w * 3]
            marks = [x for x in range(w) if min(row[x * 3:x * 3 + 3]) < white]
            if not marks:
                continue
            top = min(top, y)
            bottom = y
            left = min(left, marks[0])
            right = max(right, marks[-1])
        return None if bottom < 0 else (left, top, right, bottom)

    def margins_pt(self, white=245):
        box = self.ink_box(white)
        if not box:
            return None
        left, top, right, bottom = box
        return {'left': self.pt(left), 'top': self.pt(top),
                'right': self.pt(self.width - 1 - right),
                'bottom': self.pt(self.height - 1 - bottom)}


def render(path, page=1, dpi=72):
    """Render one page and return it as a :class:`Raster`."""
    # No output name at all is how `pdftoppm` writes to stdout. Passing `-` --
    # which is stdout for every other poppler tool -- makes it write a file
    # called `--1.ppm` into the working directory and print nothing.
    ppm = poppler.run('pdftoppm', ['-r', str(dpi), '-f', str(page), '-l', str(page),
                                   path], binary=True)
    return _read_ppm(ppm, dpi)


def _read_ppm(blob, dpi=72):
    """Parse a binary PPM (``P6``). Comments are legal in the header, so tokenize."""
    if blob[:2] != b'P6':
        raise ValueError('not a binary PPM -- pdftoppm wrote %r' % blob[:16])
    fields, i = [], 2
    while len(fields) < 3:
        while i < len(blob) and blob[i:i + 1].isspace():
            i += 1
        if blob[i:i + 1] == b'#':
            while blob[i:i + 1] not in (b'\n', b''):
                i += 1
            continue
        start = i
        while i < len(blob) and not blob[i:i + 1].isspace():
            i += 1
        fields.append(int(blob[start:i]))
    width, height, _ = fields
    return Raster(width, height, blob[i + 1:], dpi)


def fills(raster, min_pixels=400, grey=24, white=245):
    """The flat colours on the page: highlighter, shaded blocks, coloured rules.

    Anti-aliased text edges are coloured too, but there are few of them, so a
    pixel count cut-off separates a pen stroke from a letter's fringe. Greys are
    dropped (``max - min < grey``) because black text on white paper antialiases
    through grey, and so does a hairline rule.

    Returns ``[{'rgb', 'pixels', 'box'}]``, most pixels first, where ``box`` is
    ``(left, top, right, bottom)`` in pixels.
    """
    w, h, data = raster.width, raster.height, raster.data
    tally = {}
    for y in range(h):
        row = data[y * w * 3:(y + 1) * w * 3]
        for x in range(w):
            r, g, b = row[x * 3], row[x * 3 + 1], row[x * 3 + 2]
            if min(r, g, b) >= white or max(r, g, b) - min(r, g, b) < grey:
                continue
            got = tally.get((r, g, b))
            if got is None:
                tally[(r, g, b)] = [1, x, y, x, y]
            else:
                got[0] += 1
                got[1] = min(got[1], x)
                got[3] = max(got[3], x)
                got[4] = y
    out = [{'rgb': '#%02X%02X%02X' % rgb, 'pixels': v[0], 'box': (v[1], v[2], v[3], v[4])}
           for rgb, v in tally.items() if v[0] >= min_pixels]
    out.sort(key=lambda d: -d['pixels'])
    return out


def form(path, page=1, dpi=72, min_pixels=400):
    """Everything you need to rebuild the template, in one dict."""
    info = poppler.info(path)
    sheet = render(path, page, dpi)
    return {
        'pages': int(info.get('Pages', 0) or 0),
        'size_pt': poppler.page_size(path),
        'size_name': info.get('Page size', ''),
        'producer': info.get('Producer', ''),
        'fonts': poppler.fonts(path),
        'margins_pt': sheet.margins_pt(),
        'fills': fills(sheet, min_pixels=min_pixels),
        'dpi': dpi,
    }
