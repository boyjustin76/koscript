# -*- coding: utf-8 -*-
"""되돌려 맞추기 — 라이브러리가 **실제 작업 파일**에서 예전과 같은 결과를 내는지.

표본으로 지은 문서만 통과하면 소용없다. 사람이 워드로 만져 런이 잘게 쪼개진 진짜 문서에서
같은 답이 나와야 추출이 성공한 것이다.

이 시험은 회사 파일이 있어야 돌아간다. **없으면 건너뛴다** — 저장소에는 파일을 올리지 않는다.
경로는 환경변수 `SCRIPTKIT_실파일` 로 준다 (폴더 하나).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scriptkit.docx import diff, pack, read   # noqa: E402

실폴더 = os.environ.get('SCRIPTKIT_실파일')
pytestmark = pytest.mark.skipif(not 실폴더 or not os.path.isdir(실폴더),
                                reason='SCRIPTKIT_실파일 폴더가 없다 — 건너뛴다')


def 뜯기(tmp, 이름):
    길 = os.path.join(실폴더, 이름)
    if not os.path.exists(길):
        pytest.skip('%s 가 없다' % 이름)
    return pack.본문읽기(pack.풀기(길, os.path.join(str(tmp), 이름 + '.푼것')))


def test_풀고_다시_묶어도_본문이_한_글자도_안_바뀐다(tmp_path):
    이름 = '마02_테스타 이동평균선(최종)_스크립트.docx'
    길 = os.path.join(실폴더, 이름)
    if not os.path.exists(길):
        pytest.skip('%s 가 없다' % 이름)
    푼곳 = pack.풀기(길, str(tmp_path / '푼것'))
    원본xml = pack.본문읽기(푼곳)
    다시 = pack.풀기(pack.묶기(푼곳, str(tmp_path / '다시.docx')), str(tmp_path / '푼것2'))
    assert pack.본문읽기(다시) == 원본xml


def test_사람이_남긴_표시를_그대로_읽어낸다(tmp_path):
    """표시가 **붙은 문단**과 **그 문단의 내용**이 손으로 읽은 것과 같아야 한다.

    수를 세어 걸지 않는다 — 날 XML 의 `<w:u` 태그 수와 **글자가 있는 런의 수**는 다르다
    (빈 런·`rPrChange` 안의 것이 섞인다). 한 런이 취소선과 밑줄을 함께 가지면
    `표시읽기` 는 **먼저 맞은 표식 하나**로 찍는다. 그래서 수가 아니라 내용으로 건다.
    """
    xml = 뜯기(tmp_path, '마02_테스타 이동평균선_스크립트 완성본_이정찬.docx')
    표시 = read.표시읽기(xml)
    assert len(표시) == 12, len(표시)   # 지난주 보고에 13 이라 적었는데 세어 보니 12 다
    글들 = [글 for _, 글 in 표시]
    assert any('[-무너지는 날도 있죠.-]' in g and '[_무너지' in g for g in 글들)
    assert any('[-먼저 이 사람이 누구인지부터 짚고 가겠습니다.-]' in g for g in 글들)
    # 표시가 하나도 없는 문단은 결과에 안 들어간다
    assert all('[-' in g or '[_' in g for g in 글들)


def test_표토막이_본문으로_새지_않는다(tmp_path):
    xml = 뜯기(tmp_path, '마02_테스타 이동평균선(최종)_스크립트.docx')
    for 줄 in read.줄들(xml):
        assert '<w:' not in 줄 and 'w:tblPr' not in 줄


def test_전수대조가_바뀐_곳을_다_잡는다(tmp_path):
    """팀장 판에는 취소선·빨강 말고 **표시 없이 조용히 바뀐 곳**도 있었다.

    `취소선뺌=True` 는 '지울 것' 을 실제로 뺀 모습끼리 맞댄다 — 그래야 남는 차이가
    **진짜 바뀐 내용**이다.
    """
    내 = 뜯기(tmp_path, '과거/마02_테스타 이동평균선(최종)_스크립트_3판_팀장피드백전.docx')
    팀 = 뜯기(tmp_path, '마02_테스타 이동평균선(최종)_스크립트_피드백.docx')
    지움, 넣음 = diff.바뀐줄(내, 팀, 취소선뺌=True)
    assert 지움 and 넣음
    # 팀장이 새로 쓴 INTRO 가 '넣은 줄' 로 잡혀야 한다
    assert any('여러분들은 차트를 켜면' in l for l in 넣음)
    assert any('트레이딩의 성공률을 좌우합니다' in l for l in 넣음)
    # 취소선 그은 옛 INTRO 는 '지운 줄' 로
    assert any('확신이 안 서는 겁니다' in l for l in 지움)
