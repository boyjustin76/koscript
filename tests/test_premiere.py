# -*- coding: utf-8 -*-
"""premiere tests. Every assertion here corresponds to an import Premiere refused."""
import gzip
import os
import re
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from koscript.premiere import fcp7, project   # noqa: E402


def spec(**kw):
    base = {
        'name': 'seq', 'fps': 29.97, 'width': 1920, 'height': 1080,
        'sources': {'cam': {'path': 'C:/media/a (1) [x] & y.mp4', 'dur': 100.0}},
        'cuts': [{'src': 'cam', 'in': 1.0, 'out': 3.0},
                 {'src': 'cam', 'in': 10.0, 'out': 12.5}],
    }
    base.update(kw)
    return base


# ── rule 1: pathurl ────────────────────────────────────────────────────────
def test_drive_colon_is_percent_encoded_lowercase():
    u = fcp7.pathurl('C:/media/a.mp4')
    assert u.startswith('file://localhost/C%3a/')
    assert '%3A' not in u              # 대문자 16진은 프리미어 표기가 아니다


def test_brackets_and_ampersand_stay_literal():
    """퍼센트로 바꾸면 프리미어가 경로를 못 찾고, 클립이 많으면 가져오기가 통째로 깨진다."""
    u = fcp7.pathurl('C:/media/a (1) [x] & y.mp4')
    for ch in '()[]&':
        assert ch in u
    assert '%28' not in u and '%5B' not in u and '%26' not in u


def test_spaces_are_encoded():
    assert '%20' in fcp7.pathurl('C:/media/a b.mp4')


def test_windows_path_is_not_prefixed_with_cwd():
    """리눅스에서 abspath 를 거치면 `file://localhost/home/…/C:/…` 이 된다."""
    u = fcp7.pathurl('C:/media/a.mp4')
    assert u.count('C%3a') == 1 and 'home' not in u


# ── rule 2 & 3: frame arithmetic ───────────────────────────────────────────
def _clips(xml):
    root = ET.fromstring(xml)
    return root.findall('.//clipitem')


def test_timeline_length_equals_source_length():
    xml, _ = fcp7.build(spec())
    for c in _clips(xml):
        n = lambda t: int(c.find(t).text)   # noqa: E731
        assert n('end') - n('start') == n('out') - n('in')


def test_out_never_passes_the_end_of_the_media():
    xml, _ = fcp7.build(spec(cuts=[{'src': 'cam', 'in': 99.0, 'out': 120.0}]))
    media_frames = int(_clips(xml)[0].find('duration').text)
    assert int(_clips(xml)[0].find('out').text) <= media_frames


def test_a_cut_entirely_past_the_media_is_dropped():
    xml, _ = fcp7.build(spec(cuts=[{'src': 'cam', 'in': 500.0, 'out': 510.0}]))
    assert _clips(xml) == []


# ── rule 4: timebase ───────────────────────────────────────────────────────
def test_a_240fps_source_is_written_at_the_sequence_timebase():
    s = spec()
    s['sources']['cam']['fps'] = 240
    xml, _ = fcp7.build(s)
    for tb in re.findall(r'<timebase>(\d+)</timebase>', xml):
        assert int(tb) in fcp7.VALID_TIMEBASES


def test_ntsc_flag_follows_the_frame_rate():
    assert fcp7.rate(29.97) == (30, 'TRUE')
    assert fcp7.rate(30) == (30, 'FALSE')
    assert fcp7.rate(25) == (25, 'FALSE')


# ── rule 5 & 6: track layout ───────────────────────────────────────────────
def test_clips_never_overlap_within_a_track():
    xml, _ = fcp7.build(spec(cuts=[
        {'src': 'cam', 'in': 0.0, 'out': 2.0, 'track': 2, 'at': 0.0},
        {'src': 'cam', 'in': 5.0, 'out': 7.0, 'track': 2, 'at': 1.99},
    ]))
    track = ET.fromstring(xml).findall('.//video/track')[1]
    spans = [(int(c.find('start').text), int(c.find('end').text))
             for c in track.findall('clipitem')]
    for (_, e), (s2, _) in zip(spans, spans[1:]):
        assert s2 >= e


def test_clips_are_written_in_start_order():
    xml, _ = fcp7.build(spec(cuts=[
        {'src': 'cam', 'in': 0.0, 'out': 1.0, 'track': 2, 'at': 9.0},
        {'src': 'cam', 'in': 0.0, 'out': 1.0, 'track': 2, 'at': 1.0},
    ]))
    track = ET.fromstring(xml).findall('.//video/track')[1]
    starts = [int(c.find('start').text) for c in track.findall('clipitem')]
    assert starts == sorted(starts)


# ── structure ──────────────────────────────────────────────────────────────
def test_the_xml_parses():
    xml, _ = fcp7.build(spec())
    assert ET.fromstring(xml).get('version') == '4'


def test_the_source_file_is_described_once_then_referenced_by_id():
    xml, _ = fcp7.build(spec())
    assert xml.count('<pathurl>') == 1
    assert xml.count('<file id="file-1"/>') >= 1


def test_markers_sit_directly_under_sequence():
    xml, _ = fcp7.build(spec(markers=[{'at': 1.0, 'name': 'clap', 'dur': 0}]))
    seq = ET.fromstring(xml).find('sequence')
    assert [m.find('name').text for m in seq.findall('marker')] == ['clap']


def test_a_point_marker_has_out_minus_one():
    xml, _ = fcp7.build(spec(markers=[{'at': 1.0, 'name': 'x'}]))
    assert ET.fromstring(xml).find('sequence/marker/out').text == '-1'


def test_disabled_clips_mute_their_audio_too():
    xml, _ = fcp7.build(spec(cuts=[{'src': 'cam', 'in': 0.0, 'out': 1.0, 'enabled': False}]))
    assert all(c.find('enabled').text == 'FALSE' for c in _clips(xml))


def test_thin_mode_drops_the_links():
    full, _ = fcp7.build(spec())
    thin, _ = fcp7.build(spec(), thin=True)
    assert '<link>' in full and '<link>' not in thin


def test_an_upper_track_clip_without_at_is_rejected():
    with pytest.raises(fcp7.BadCut, match='"at"'):
        fcp7.build(spec(cuts=[{'src': 'cam', 'in': 0.0, 'out': 1.0, 'track': 2}]))


def test_an_unknown_source_is_rejected_by_name():
    with pytest.raises(fcp7.BadCut, match='nope'):
        fcp7.build(spec(cuts=[{'src': 'nope', 'in': 0.0, 'out': 1.0}]))


def test_xml_special_characters_are_escaped():
    s = spec(name='a & b')
    s['cuts'][0]['label'] = '<tag>'
    xml, _ = fcp7.build(s)
    assert ET.fromstring(xml).find('sequence/name').text == 'a & b'


# ── project reading ────────────────────────────────────────────────────────
def _prproj(path, inner):
    with gzip.open(path, 'wb') as f:
        f.write(('<PremiereData>%s</PremiereData>' % inner).encode('utf-8'))
    return str(path)


def test_reads_a_gzipped_project(tmp_path):
    p = _prproj(tmp_path / 'p.prproj', '<FilePath>C:\\a\\b.mp4</FilePath>')
    assert 'b.mp4' in project.read_xml(p)


def test_reads_an_uncompressed_project(tmp_path):
    p = tmp_path / 'plain.prproj'
    p.write_text('<PremiereData><FilePath>C:\\a\\b.mp4</FilePath></PremiereData>',
                 encoding='utf-8')
    assert 'b.mp4' in project.read_xml(str(p))


def test_relative_paths_are_unescaped_twice(tmp_path):
    """한 번만 풀면 `&` 가 든 멀쩡한 클립을 끊긴 걸로 읽는다."""
    media = tmp_path / 'a & b.mp4'
    media.write_text('x', encoding='utf-8')
    p = _prproj(tmp_path / 'p.prproj', '<RelativePath>a &amp;amp; b.mp4</RelativePath>')
    _, relative = project.links(p)
    assert 'a & b.mp4' in relative


def test_a_clip_found_by_relative_path_is_not_offline(tmp_path):
    media = tmp_path / 'b.mp4'
    media.write_text('x', encoding='utf-8')
    p = _prproj(tmp_path / 'p.prproj',
                '<ActualMediaFilePath>Z:\\gone\\b.mp4</ActualMediaFilePath>'
                '<RelativePath>b.mp4</RelativePath>')
    gone, total = project.offline(p)
    assert gone == [] and total == 1


def test_a_truly_missing_clip_is_reported(tmp_path):
    p = _prproj(tmp_path / 'p.prproj',
                '<ActualMediaFilePath>Z:\\gone\\nope.mp4</ActualMediaFilePath>')
    gone, _ = project.offline(p)
    assert gone == ['Z:\\gone\\nope.mp4']


def test_referencing_finds_who_points_at_a_path(tmp_path):
    _prproj(tmp_path / 'uses.prproj',
            '<ActualMediaFilePath>C:\\shared\\clips\\x.mp4</ActualMediaFilePath>')
    _prproj(tmp_path / 'other.prproj',
            '<ActualMediaFilePath>C:\\elsewhere\\y.mp4</ActualMediaFilePath>')
    hits = project.referencing('shared\\clips', str(tmp_path))
    assert len(hits) == 1 and 'uses.prproj' in hits[0][0]


def test_autosave_copies_are_skipped_unless_asked(tmp_path):
    folder = tmp_path / 'Adobe Premiere Pro Auto-Save'
    folder.mkdir()
    _prproj(folder / 'p.prproj', '<FilePath>C:\\a\\b.mp4</FilePath>')
    assert list(project.projects(str(tmp_path))) == []
    assert len(list(project.projects(str(tmp_path), include_autosave=True))) == 1
