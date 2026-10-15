# -*- coding: utf-8 -*-
"""Unpack a ``.docx`` into a folder and pack it back.

A ``.docx`` is a zip of XML parts. To change one you unpack it, edit
``word/document.xml``, and zip it again.

``[Content_Types].xml`` must be the **first entry** in the zip or Word refuses to
open the file. Plain alphabetical order puts ``_rels`` first, which produces a file
that looks fine to most tools and dead to Word -- so the order is forced here.

Windows often has no ``zip`` binary, so everything goes through ``zipfile``.
"""
import os
import shutil
import zipfile

CONTENT_TYPES = '[Content_Types].xml'


def unpack(docx_path, out_dir, overwrite=True):
    """Unpack ``docx_path`` into ``out_dir``. Returns ``out_dir``.

    Symlink entries are removed: a zip from an untrusted source can use them to
    write outside the folder.
    """
    if overwrite and os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(docx_path) as z:
        z.extractall(out_dir)
    for root, _, names in os.walk(out_dir):
        for n in names:
            p = os.path.join(root, n)
            if os.path.islink(p):
                os.unlink(p)
    return out_dir


def repack(src_dir, out_path):
    """Zip an unpacked folder back into a ``.docx``. Returns ``out_path``."""
    entries = []
    for root, _, names in os.walk(src_dir):
        for n in names:
            p = os.path.join(root, n)
            entries.append((os.path.relpath(p, src_dir).replace('\\', '/'), p))
    if not any(name == CONTENT_TYPES for name, _ in entries):
        raise ValueError('no %s here -- is this an unpacked .docx?' % CONTENT_TYPES)
    entries.sort(key=lambda e: (e[0] != CONTENT_TYPES, e[0]))

    if os.path.exists(out_path):
        os.remove(out_path)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, p in entries:
            z.write(p, name)
    return out_path


def body_path(src_dir):
    """Path of ``word/document.xml`` inside an unpacked folder."""
    return os.path.join(src_dir, 'word', 'document.xml')


def read_body(src_dir):
    with open(body_path(src_dir), encoding='utf-8') as f:
        return f.read()


def write_body(src_dir, xml):
    with open(body_path(src_dir), 'w', encoding='utf-8') as f:
        f.write(xml)
