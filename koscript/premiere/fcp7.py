# -*- coding: utf-8 -*-
"""Build an FCP7 XML (``xmeml`` v4) sequence that Premiere Pro will actually import.

Premiere's failure mode is binary and uninformative: it refuses the whole file with
*"the project is damaged and cannot be opened"*. It never says which clip is wrong.
Worse, several of the causes below only bite once the file is large enough, so a
three-cut test passes and a seventy-cut edit fails -- which makes it look like a
clip-count limit. It is not.

Each rule here was found by bisecting a failing import against an XML Premiere had
exported itself.

**1. ``pathurl`` encoding.** The big one. Premiere writes the drive colon as ``%3a``,
uses **lowercase** hex, and leaves ``( ) [ ] &`` **literal**. Percent-encode brackets
and Premiere cannot find the media; with many clips, the temporary project conversion
then fails outright.

**2. ``end - start`` must equal ``out - in``.** Round the timeline position and the
source range separately and they drift a frame apart. Premiere rejects the file.

**3. ``out`` must not exceed the media length.** Round the last frame *up* and you
land past the end of the file. Floor it.

**4. ``timebase`` is 24/25/30/50/60 only.** A 240 fps phone clip written as
``<timebase>240</timebase>`` fails the import. Write the sequence timebase instead and
count in/out as ``seconds x sequence fps``; the positions still land correctly.

**5. No overlap inside one track**, not even one frame.

**6. Clips must be written in start order** within a track. Out-of-order clips import
but most of them do not show, and the ones that do flicker.
"""
import html
import math
import os
import re
from urllib.parse import quote

from .project import file_name

#: Characters Premiere leaves literal in a ``pathurl`` -- measured from its own export.
SAFE = "/()[]&~!$'*+,;=@_-."

#: Timebases FCP7 XML accepts.
VALID_TIMEBASES = (24, 25, 30, 50, 60)


def rate(fps):
    """``29.97 -> (30, 'TRUE')``, ``30 -> (30, 'FALSE')``."""
    tb = int(round(fps))
    return tb, ('TRUE' if abs(fps - tb) > 0.001 else 'FALSE')


def frames(seconds, fps):
    return int(round(seconds * fps))


def pathurl(path):
    """A file URL in exactly the form Premiere writes.

    Drive colon encoded (``C%3a/``), hex in lowercase, brackets and ``&`` left alone.
    Get this wrong and the import fails with no useful message.
    """
    # 드라이브 문자로 시작하는 윈도우 경로는 abspath 를 거치지 않는다 — 리눅스에서 돌리면
    # abspath 가 앞에 cwd 를 붙여 `file://localhost/home/…/C:/…` 이 된다
    if not re.match(r'^[A-Za-z]:[\\/]', path):
        path = os.path.abspath(path)
    path = path.replace('\\', '/')
    url = quote(path.lstrip('/'), safe=SAFE)          # ':' 는 safe 에 넣지 않는다 → %3a
    url = re.sub(r'%[0-9A-F]{2}', lambda m: m.group(0).lower(), url)
    return 'file://localhost/' + url


class BadCut(ValueError):
    """A cut that cannot be written -- the message says which one and why."""


def build(spec, source_root=None, thin=False):
    """``(xml, {track: [clips]})`` from a cut list.

    ``spec``::

        {"name": "sequence", "fps": 29.97, "width": 1920, "height": 1080,
         "sources": {"cam": {"path": "/a/cam.mp4", "dur": 882.2, "fps": 240}},
         "cuts": [{"src": "cam", "in": 1.2, "out": 5.0},
                  {"src": "cam", "in": 300.0, "out": 312.5,
                   "track": 2, "at": 40.1, "audio": False, "enabled": False}],
         "markers": [{"at": 12.0, "name": "clap", "comment": "", "dur": 0}]}

    A single-source list may use ``"source"``/``"src_dur"`` instead of ``"sources"``.
    ``in``/``out`` are seconds in the source. Track 1 video cuts are laid end to end;
    anything else needs ``at`` (its start on the timeline).

    ``source_root`` re-points the sources at another folder, keeping the file names --
    for when the cut list was made on a different machine.

    ``thin=True`` omits the audio/video ``<link>`` elements. Links are what makes a
    clip grab as one piece in Premiere, but they also make a malformed file harder to
    diagnose, so drop them while you are bisecting an import failure.
    """
    fps = float(spec.get('fps', 29.97))
    tb, ntsc = rate(fps)
    width = int(spec.get('width', 1920))
    height = int(spec.get('height', 1080))
    name = spec.get('name', 'sequence')
    R = '<rate><timebase>%d</timebase><ntsc>%s</ntsc></rate>' % (tb, ntsc)
    DF = 'DF' if ntsc == 'TRUE' else 'NDF'

    sources = {k: dict(v) for k, v in (spec.get('sources') or {}).items()}
    if 'source' in spec:
        sources.setdefault('_main', {'path': spec['source'],
                                     'dur': float(spec.get('src_dur', 0))})
    if not sources:
        raise BadCut('no sources: give "sources" or "source"')
    if source_root:
        for v in sources.values():
            p = os.path.join(source_root, os.path.basename(v['path'].replace('\\', '/')))
            if not os.path.exists(p):
                raise BadCut('source not found under source_root: %s' % p)
            v['path'] = p

    fid = {k: 'file-%d' % i for i, k in enumerate(sorted(sources), 1)}
    # 규칙 4 — 60 을 넘는 원본 박자는 시퀀스 박자로 적는다
    src_fps = {k: (float(v['fps']) if v.get('fps') and float(v['fps']) <= 60.5 else fps)
               for k, v in sources.items()}
    # 규칙 3 — 끝 프레임은 **내림**. 반올림하면 미디어 끝을 몇 프레임 넘는다
    src_frames = {k: max(1, math.floor(float(v.get('dur', 0)) * src_fps[k]))
                  for k, v in sources.items()}
    written = set()

    def file_ref(k):
        """원본은 처음 한 번만 자세히 적고, 뒤에서는 id 로만 가리킨다."""
        if k in written:
            return '<file id="%s"/>' % fid[k]
        written.add(k)
        p = sources[k]['path']
        ftb, fntsc = rate(src_fps[k])
        FR = '<rate><timebase>%d</timebase><ntsc>%s</ntsc></rate>' % (ftb, fntsc)
        return (
            '<file id="%s"><name>%s</name><pathurl>%s</pathurl>%s<duration>%d</duration>'
            '<timecode>%s<string>00:00:00:00</string><frame>0</frame>'
            '<displayformat>%s</displayformat></timecode>'
            '<media><video><samplecharacteristics>%s<width>%d</width><height>%d</height>'
            '<pixelaspectratio>square</pixelaspectratio><anamorphic>FALSE</anamorphic>'
            '</samplecharacteristics></video>'
            '<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate>'
            '</samplecharacteristics><channelcount>2</channelcount></audio></media></file>'
            # Not `os.path.basename`: a Windows path handed in on a Mac would come
            # back whole and the clip would be named after its full path.
            % (fid[k], html.escape(file_name(p)), html.escape(pathurl(p)), FR,
               src_frames[k], R, DF, R, width, height))

    tracks, cursor, end_max = {}, 0, 0
    for i, c in enumerate(spec['cuts'], 1):
        k = c.get('src', '_main')
        if k not in sources:
            raise BadCut('cut %d: source %r is not in "sources"' % (i, k))
        in_f = frames(float(c['in']), src_fps[k])
        # 시작이 이미 미디어 밖이면 **통째로 버린다.** 끝만 잘라 붙이면 10초짜리 컷이
        # 1프레임 클립으로 남아, 조용히 생긴 쓰레기를 나중에 눈으로 찾게 된다.
        if in_f >= src_frames[k]:
            continue
        out_f = min(frames(float(c['out']), src_fps[k]), src_frames[k])   # 끝만 넘치면 자른다
        if out_f <= in_f:
            continue
        # 규칙 2 — 타임라인 길이는 원본 구간 길이에서 그대로 가져온다. 따로 세지 않는다.
        n = out_f - in_f
        track = int(c.get('track', 1))
        has_audio, has_video = c.get('audio', True), c.get('video', True)
        if not (has_audio or has_video):
            continue
        if 'at' in c:
            start = frames(float(c['at']), fps)
        elif track == 1 and has_video:
            start = cursor
        else:
            raise BadCut('cut %d: a V%d or audio-only clip needs "at"' % (i, track))
        end = start + n
        if track == 1 and has_video:
            cursor = end
        end_max = max(end_max, end)

        label = html.escape(c.get('label') or 'cut%d' % i)
        vid, a1, a2 = 'cv%d' % i, 'ca%da' % i, 'ca%db' % i
        base = {'s': start, 'e': end, 'in': in_f, 'out': out_f, 'k': k, 'label': label,
                'linked': (vid, a1, a2) if (has_audio and has_video) else None,
                'en': 'TRUE' if c.get('enabled', True) else 'FALSE'}
        if has_video:
            tracks.setdefault(('v', track), []).append(dict(base, id=vid))
        if has_audio:
            # 소리도 영상과 같이 끈다 — 안 쓰는 테이크 소리가 울리면 안 된다
            for ch, aid in ((1, a1), (2, a2)):
                tracks.setdefault(('a', ch), []).append(dict(base, id=aid))

    # 규칙 6 — 트랙 안에서 시작 순서로. 규칙 5 — 겹치면 뒤로 민다.
    for clips in tracks.values():
        clips.sort(key=lambda x: x['s'])
        for left, right in zip(clips, clips[1:]):
            if right['s'] < left['e']:
                shift = left['e'] - right['s']
                right['s'] += shift
                right['e'] += shift
                end_max = max(end_max, right['e'])
    where = {x['id']: (key[1], j)
             for key, clips in tracks.items() for j, x in enumerate(clips, 1)}

    def link(x):
        if not x['linked'] or thin:
            return ''
        vid, a1, a2 = x['linked']
        (vt, vi), (_, i1), (_, i2) = where[vid], where[a1], where[a2]
        return ('<link><linkclipref>%s</linkclipref><mediatype>video</mediatype>'
                '<trackindex>%d</trackindex><clipindex>%d</clipindex></link>'
                '<link><linkclipref>%s</linkclipref><mediatype>audio</mediatype>'
                '<trackindex>1</trackindex><clipindex>%d</clipindex>'
                '<groupindex>1</groupindex></link>'
                '<link><linkclipref>%s</linkclipref><mediatype>audio</mediatype>'
                '<trackindex>2</trackindex><clipindex>%d</clipindex>'
                '<groupindex>1</groupindex></link>' % (vid, vt, vi, a1, i1, a2, i2))

    def clip_rate(k):
        ftb, fntsc = rate(src_fps[k])
        return '<rate><timebase>%d</timebase><ntsc>%s</ntsc></rate>' % (ftb, fntsc)

    def head(x):
        return ('<clipitem id="%s"><name>%s</name><enabled>%s</enabled>'
                '<duration>%d</duration>%s<start>%d</start><end>%d</end>'
                '<in>%d</in><out>%d</out>%s'
                % (x['id'], x['label'], x['en'], src_frames[x['k']], clip_rate(x['k']),
                   x['s'], x['e'], x['in'], x['out'], file_ref(x['k'])))

    def vclip(x):
        return head(x) + '<compositemode>normal</compositemode>' + link(x) + '</clipitem>'

    def aclip(x, ch):
        return (head(x) + '<sourcetrack><mediatype>audio</mediatype>'
                '<trackindex>%d</trackindex></sourcetrack>' % ch + link(x) + '</clipitem>')

    def marker(m):
        s = frames(float(m['at']), fps)
        e = s + frames(float(m.get('dur', 0)), fps)
        return ('<marker><name>%s</name><comment>%s</comment><in>%d</in><out>%d</out>'
                '</marker>' % (html.escape(str(m.get('name', ''))),
                               html.escape(str(m.get('comment', ''))),
                               s, e if e > s else -1))

    # 마커는 **`<sequence>` 바로 아래**에 둔다. 다른 자리에 두면 조용히 사라진다.
    markers = ''.join(marker(m) for m in spec.get('markers', []))

    nv = max([t for kind, t in tracks if kind == 'v'] or [1])
    video_tracks = {t: tracks.get(('v', t), []) for t in range(1, nv + 1) if ('v', t) in tracks}
    vxml = ''.join('<track>%s</track>'
                   % ''.join(vclip(x) for x in tracks.get(('v', t), []))
                   for t in range(1, nv + 1))

    def atrack(ch):
        return ('<track>%s<outputchannelindex>%d</outputchannelindex></track>'
                % (''.join(aclip(x, ch) for x in tracks.get(('a', ch), [])), ch))

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">\n'
           '<sequence id="%s"><name>%s</name><duration>%d</duration>%s'
           '<timecode>%s<string>00:00:00:00</string><frame>0</frame>'
           '<displayformat>%s</displayformat></timecode>'
           '<media><video><format><samplecharacteristics>%s<width>%d</width>'
           '<height>%d</height><pixelaspectratio>square</pixelaspectratio>'
           '<anamorphic>FALSE</anamorphic></samplecharacteristics></format>%s</video>'
           '<audio><numOutputChannels>2</numOutputChannels><format>'
           '<samplecharacteristics><depth>16</depth><samplerate>48000</samplerate>'
           '</samplecharacteristics></format>%s%s</audio></media>%s</sequence>\n</xmeml>\n'
           % (html.escape(name), html.escape(name), end_max, R, R, DF, R, width, height,
              vxml, atrack(1), atrack(2), markers))
    return xml, video_tracks
