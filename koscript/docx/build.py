# -*- coding: utf-8 -*-
"""Write ``word/document.xml`` by hand.

Why by hand: the usual document libraries cannot open an existing file and keep a
producer's template intact. When you have to reproduce someone else's layout
exactly, writing OOXML directly is the shorter road.

**The thing you need to know:** the order of children inside ``<w:pPr>`` and
``<w:rPr>`` is fixed by the schema. It looks like it should not matter -- it does.
Word rejects the file with ``Element 'spacing': This element is not expected``.
This module enforces the order:

    pPr : pBdr -> shd -> spacing -> ind -> jc
    rPr : rFonts -> b -> i -> strike -> color -> spacing -> sz -> szCs -> u -> shd

Sizes are in half-points (20 = 10pt); lengths are in twips (1440 = 1 inch).
"""

_ESCAPES = (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'))

A4 = (11906, 16838)
LETTER = (12240, 15840)

_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')


def esc(s):
    for a, b in _ESCAPES:
        s = s.replace(a, b)
    return s


def run(text, font=None, bold=False, italic=False, strike=False, underline=False,
        color=None, spacing=None, size=None, fill=None):
    """One run of text. ``spacing`` is letter spacing; ``fill`` is a highlight colour."""
    rpr = []
    if font:
        rpr.append('<w:rFonts w:ascii="{0}" w:eastAsia="{0}" w:hAnsi="{0}" w:cs="{0}"/>'
                   .format(esc(font)))
    if bold:
        rpr.append('<w:b/><w:bCs/>')
    if italic:
        rpr.append('<w:i/><w:iCs/>')
    if strike:
        rpr.append('<w:strike/>')
    if color:
        rpr.append('<w:color w:val="%s"/>' % color)
    if spacing:
        rpr.append('<w:spacing w:val="%d"/>' % spacing)
    if size:
        rpr.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size))
    if underline:
        rpr.append('<w:u w:val="single"/>')
    if fill:
        rpr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill)
    props = '<w:rPr>%s</w:rPr>' % ''.join(rpr) if rpr else ''
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (props, esc(text))


def para(runs, before=0, after=0, line=None, border=None, fill=None,
         indent=0, right_indent=0, center=False):
    """``runs`` is one string or a list of ``run()`` results. ``line`` 240 = single."""
    ppr = []
    if border:
        ppr.append('<w:pBdr><w:%s w:val="single" w:sz="6" w:space="6" w:color="C9D0D6"/>'
                   '</w:pBdr>' % border)
    if fill:
        ppr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill)
    ppr.append('<w:spacing w:before="%d" w:after="%d"%s/>' % (
        before, after, (' w:line="%d" w:lineRule="auto"' % line) if line else ''))
    if indent or right_indent:
        ppr.append('<w:ind w:left="%d" w:right="%d"/>' % (indent, right_indent))
    if center:
        ppr.append('<w:jc w:val="center"/>')
    body = runs if isinstance(runs, str) else ''.join(runs)
    return '<w:p><w:pPr>%s</w:pPr>%s</w:p>' % (''.join(ppr), body)


def cell(paras, width, fill=None, border_color='BBBBBB', margin=80):
    tcpr = ['<w:tcW w:w="%d" w:type="dxa"/>' % width]
    if border_color:
        tcpr.append('<w:tcBorders>%s</w:tcBorders>' % ''.join(
            '<w:%s w:val="single" w:sz="4" w:space="0" w:color="%s"/>' % (side, border_color)
            for side in ('top', 'left', 'bottom', 'right')))
    if fill:
        tcpr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill)
    tcpr.append('<w:tcMar><w:top w:w="%d" w:type="dxa"/><w:left w:w="%d" w:type="dxa"/>'
                '<w:bottom w:w="%d" w:type="dxa"/><w:right w:w="%d" w:type="dxa"/></w:tcMar>'
                % (margin, margin + 40, margin, margin + 40))
    tcpr.append('<w:vAlign w:val="center"/>')
    body = paras if isinstance(paras, str) else ''.join(paras)
    return '<w:tc><w:tcPr>%s</w:tcPr>%s</w:tc>' % (''.join(tcpr), body)


def row(cells_, header=False):
    """``header=True`` repeats the row at the top of every page."""
    trpr = '<w:trPr><w:tblHeader/></w:trPr>' if header else ''
    return '<w:tr>%s%s</w:tr>' % (trpr, ''.join(cells_))


def table(rows, widths):
    """Fixed layout -- otherwise Word re-computes the column widths on open."""
    grid = ''.join('<w:gridCol w:w="%d"/>' % w for w in widths)
    return ('<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/>'
            '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>%s</w:tblGrid>%s</w:tbl>'
            % (sum(widths), grid, ''.join(rows)))


def section(page=A4, margin=1440, landscape=False, header_id=None, top=None, bottom=None):
    w, h = (page[1], page[0]) if landscape else page
    orient = ' w:orient="landscape"' if landscape else ''
    hdr = '<w:headerReference w:type="default" r:id="%s"/>' % header_id if header_id else ''
    return ('<w:sectPr>%s<w:pgSz w:w="%d" w:h="%d"%s/>'
            '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
            'w:header="700" w:footer="700" w:gutter="0"/></w:sectPr>'
            % (hdr, w, h, orient, top or margin, margin, bottom or margin, margin))


def document(body, section_xml=None):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document %s><w:body>%s%s</w:body></w:document>'
            % (_NS, body if isinstance(body, str) else ''.join(body),
               section_xml or section()))


def add_header(src_dir, header_paragraph_xml, rid='rIdHdr', filename='header9.xml'):
    """Add a running page header. Pair with ``section(header_id=rid)``.

    세 군데를 같이 손봐야 워드가 인정한다 — 머리말 파일, 관계 목록, 종류 목록.
    """
    import os
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<w:hdr %s>%s</w:hdr>' % (_NS, header_paragraph_xml))
    with open(os.path.join(src_dir, 'word', filename), 'w', encoding='utf-8') as f:
        f.write(xml)

    rels = os.path.join(src_dir, 'word', '_rels', 'document.xml.rels')
    with open(rels, encoding='utf-8') as f:
        r = f.read()
    if filename not in r:
        r = r.replace('</Relationships>',
                      '<Relationship Id="%s" Type="http://schemas.openxmlformats.org/'
                      'officeDocument/2006/relationships/header" Target="%s"/>'
                      '</Relationships>' % (rid, filename))
        with open(rels, 'w', encoding='utf-8') as f:
            f.write(r)

    ct = os.path.join(src_dir, '[Content_Types].xml')
    with open(ct, encoding='utf-8') as f:
        c = f.read()
    if filename not in c:
        c = c.replace('</Types>',
                      '<Override PartName="/word/%s" ContentType="application/'
                      'vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
                      '</Types>' % filename)
        with open(ct, 'w', encoding='utf-8') as f:
            f.write(c)
    return rid
