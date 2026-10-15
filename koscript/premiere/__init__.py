# -*- coding: utf-8 -*-
"""Hand an edit to Premiere Pro, and read what Premiere already has.

``fcp7``    build an FCP7 XML sequence Premiere will import
``project`` read a ``.prproj`` (gzipped XML) without opening Premiere
"""
from . import fcp7, project
from .fcp7 import BadCut, build, pathurl, rate
from .project import links, offline, read_xml, referencing

__all__ = ['fcp7', 'project', 'build', 'pathurl', 'rate', 'BadCut',
           'read_xml', 'links', 'offline', 'referencing']
