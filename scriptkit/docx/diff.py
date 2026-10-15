# -*- coding: utf-8 -*-
"""두 판을 **문단 단위로 전수 대조**한다.

사람이 손본 판이 오면 표시(취소선·밑줄)만 보고 고치면 안 된다.
**표시 없이 조용히 바뀐 곳**이 늘 있다. 실제로 겪었다 — 제목 한 줄, 어미 셋,
회차 번호가 표시 없이 바뀌어 있었다. 그래서 늘 전수로 맞대 본다.
"""
import difflib

from . import read as _읽기


def 대조(가xml, 나xml, 가이름='가', 나이름='나', 취소선뺌=False, 앞뒤=1):
    """두 본문 XML 의 문단 목록을 맞대 unified diff 줄 목록을 돌려준다.

    `취소선뺌` — 사람이 그어 놓은 '지울 것' 을 뺀 뒤의 모습으로 맞댄다.
    """
    가 = _읽기.표시적용(가xml) if 취소선뺌 else _읽기.줄들(가xml)
    나 = _읽기.표시적용(나xml) if 취소선뺌 else _읽기.줄들(나xml)
    return list(difflib.unified_diff(가, 나, 가이름, 나이름, lineterm='', n=앞뒤))


def 바뀐줄(가xml, 나xml, 취소선뺌=False):
    """(지운 줄, 넣은 줄) — 개수만 빠르게 보고 싶을 때."""
    줄 = 대조(가xml, 나xml, 취소선뺌=취소선뺌, 앞뒤=0)
    지움 = [l[1:] for l in 줄 if l.startswith('-') and not l.startswith('---')]
    넣음 = [l[1:] for l in 줄 if l.startswith('+') and not l.startswith('+++')]
    return 지움, 넣음
