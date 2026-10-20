# -*- coding: utf-8 -*-
"""Read a prompter script out of a PDF, and measure a PDF form you have to match.

``prompter`` PDF -> sections and read-aloud sentences
``probe``    page size, fonts, margins and highlight colours, measured
``poppler``  find and run the poppler binaries (the only dependency)
"""
from . import poppler, probe, prompter
from .poppler import PopplerMissing, fonts, page_size, text
from .probe import Raster, fills, form, render
from .prompter import Layout, joins, page_furniture, parse, read, split_sentences

__all__ = ['prompter', 'probe', 'poppler',
           'read', 'parse', 'split_sentences', 'joins', 'page_furniture', 'Layout',
           'form', 'fills', 'render', 'Raster', 'text', 'fonts', 'page_size',
           'PopplerMissing']
