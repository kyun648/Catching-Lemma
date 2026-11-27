"""문맥자유 펌핑 게임 스테이지 정의(JSON) 검사. 새 언어를 추가하면 이 테스트가 정의의 실수를 잡아준다."""

import pytest

from catching_lemma.engine.cfl_pumping import (
    MAX_CFL_RECEIVE_WORK,
    analyze_cfl_splits,
    cfl_case_report,
    cfl_has_winning_receive,
    cfl_receive_work,
)
from catching_lemma.engine.pumping_common import expand_template, parse_template
from catching_lemma.stages import MAX_SERVE, load_pumping_stages, load_stages

STAGES = load_pumping_stages("cfl_pumping")
NON_CFL = [s for s in STAGES if not s.context_free]
CFL = [s for s in STAGES if s.context_free]


def test_cfl_stages_exist_and_ids_unique():
    assert len(NON_CFL) >= 2 and len(CFL) >= 2
    ids = [s.id for s in load_pumping_stages(None)] + [s.id for s in load_stages()]
    assert len(ids) == len(set(ids))
    assert all(s.regular is None for s in STAGES)  # 문맥자유 장에서는 정규 여부를 다루지 않는다


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_examples_match_language(stage):
    assert stage.examples_accept and stage.examples_reject
    for word in stage.examples_accept:
        assert stage.language.contains(word), f"{word!r}는 L에 속해야 함"
    for word in stage.examples_reject:
        assert not stage.language.contains(word), f"{word!r}는 L에 속하지 않아야 함"


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_m_values_and_max_serve(stage):
    assert len(stage.m_values) >= 5 and all(m >= 1 for m in stage.m_values)
    assert 1 <= stage.max_serve <= MAX_SERVE


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_both_role_hints(stage):
    assert stage.hint and stage.hint_defend


@pytest.mark.parametrize("stage", NON_CFL, ids=lambda s: s.id)
def test_sample_receive_beats_every_defense(stage):
    blocks = parse_template(stage.sample_receive, stage.language.alphabet)
    for m in stage.m_values:
        word = expand_template(blocks, m)
        assert stage.language.contains(word) and len(word) >= m
        assert all(s.breaking for s in analyze_cfl_splits(stage.language, word, m)), f"m = {m}"


@pytest.mark.parametrize("stage", NON_CFL, ids=lambda s: s.id)
def test_sample_receive_produces_case_report(stage):
    report = cfl_case_report(stage.language, stage.sample_receive, stage.m_values)
    assert report.available, report.reason


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_context_free_flag_matches_game_behavior(stage):
    """context_free 값이 실제 게임 결과와 맞는지 확인한다.

    문맥자유가 아닌 언어: 막는 쪽이 어떤 m(1 ~ max_serve)을 서브해도 컴퓨터에게 어떤 수비든 뚫는 리시브가 있다.
    문맥자유 언어: 깨는 쪽 게임에서 Lemma가 서브하는 m(m_values)마다 막는 쪽이 모든 w를 막을 수 있다.
    """
    if stage.context_free:
        assert not stage.sample_receive
        for m in stage.m_values:
            assert not cfl_has_winning_receive(stage.language, m), f"m = {m}에서 막을 수 없는 w가 있음"
    else:
        for m in range(1, stage.max_serve + 1):
            assert cfl_has_winning_receive(stage.language, m), f"m = {m}에서 이기는 리시브가 없음"


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_defender_game_receive_stays_light(stage):
    """막는 쪽 게임에서 컴퓨터는 m = max_serve일 때 길이 m ~ 3m + 3인 후보 w의 모든 분할을 살펴본다.

    후보 수가 아니라 실제 계산량(후보마다 분할 수를 더한 값)으로 확인한다. 걸리면 스테이지의 max_serve를 낮추거나,
    조건을 좁히거나, 블록 수를 줄여주세요.
    """
    work = cfl_receive_work(stage.language, stage.max_serve)
    assert work <= MAX_CFL_RECEIVE_WORK, (
        f"m = {stage.max_serve}에서 첫 리시브 계산량이 {work:,}예요 (상한 {MAX_CFL_RECEIVE_WORK:,})."
    )
