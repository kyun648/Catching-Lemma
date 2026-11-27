"""펌핑 게임 스테이지 정의(JSON) 검사. 새 언어를 추가하면 이 테스트가 정의의 실수를 잡아준다."""

import pytest

from catching_lemma.engine.pumping import (
    MAX_RECEIVE_CANDIDATES,
    analyze_splits,
    best_receives,
    build_proof,
    regular_candidate_words,
)
from catching_lemma.engine.pumping_common import expand_template, parse_template
from catching_lemma.stages import MAX_SERVE, load_pumping_stages, load_stages

STAGES = load_pumping_stages()
NON_REGULAR = [s for s in STAGES if not s.regular]
REGULAR = [s for s in STAGES if s.regular]


def test_pumping_stages_exist():
    assert len(NON_REGULAR) >= 2
    assert len(REGULAR) >= 2


def test_pumping_stages_not_mixed_with_automaton_stages():
    assert all(s.chapter != "pumping" for s in load_stages())
    ids = [s.id for s in load_pumping_stages(None)] + [s.id for s in load_stages()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_examples_match_language(stage):
    assert stage.examples_accept and stage.examples_reject
    for word in stage.examples_accept:
        assert stage.language.contains(word), f"{word!r}는 L에 속해야 함"
    for word in stage.examples_reject:
        assert not stage.language.contains(word), f"{word!r}는 L에 속하지 않아야 함"


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_m_values_allow_three_wins(stage):
    # 3포인트를 먼저 따야 하므로 최대 5포인트(3:2)까지 필요하다
    assert len(stage.m_values) >= 5
    assert all(m >= 1 for m in stage.m_values)


@pytest.mark.parametrize("stage", NON_REGULAR, ids=lambda s: s.id)
def test_sample_receive_beats_every_defense(stage):
    """스테이지에 적은 이기는 w 예시가 실제로 모든 m, 모든 수비 코스를 이기는지."""
    blocks = parse_template(stage.sample_receive, stage.language.alphabet)
    for m in stage.m_values:
        word = expand_template(blocks, m)
        assert stage.language.contains(word) and len(word) >= m
        assert all(s.breaking for s in analyze_splits(stage.language, word, m)), f"m = {m}"


@pytest.mark.parametrize("stage", NON_REGULAR, ids=lambda s: s.id)
def test_sample_receive_produces_proof(stage):
    proof = build_proof(stage.language, stage.condition_text, stage.sample_receive, stage.m_values)
    assert proof.available, proof.reason


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_regular_flag_matches_game_behavior(stage):
    """regular 값이 실제 게임 결과와 맞는지 확인한다.

    정규가 아닌 언어: 막는 쪽이 어떤 m을 서브해도 컴퓨터에게 어떤 수비든 뚫는 리시브가 있다.
    정규 언어: 깨는 쪽 게임에서 Lemma가 서브하는 m(m_values)마다 막는 쪽이 모든 w를 막을 수 있다.
    """
    if stage.regular:
        assert not stage.sample_receive
        for m in stage.m_values:
            assert best_receives(stage.language, m)[0] == [], f"m = {m}에서 막을 수 없는 w가 있음"
    else:
        for m in range(1, stage.max_serve + 1):
            assert best_receives(stage.language, m)[0], f"m = {m}에서 이기는 리시브가 없음"


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_max_serve_in_range(stage):
    assert 1 <= stage.max_serve <= MAX_SERVE


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_both_role_hints(stage):
    assert stage.hint and stage.hint_defend


def test_readme_example_stage_id_is_not_taken():
    """README의 '언어 추가하기' 예시를 그대로 복사해도 기존 스테이지 id와 겹치지 않아야 한다."""
    import json
    import re
    from pathlib import Path

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", readme, re.S)]
    pumping = [e for e in examples if e.get("chapter") == "pumping"]
    assert pumping
    taken = {s.id for s in STAGES} | {s.id for s in load_stages()}
    for example in pumping:
        assert example["id"] not in taken


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_defender_game_receive_stays_light(stage):
    """막는 쪽 게임에서 컴퓨터는 m = max_serve일 때 후보 w를 모두 살펴본다.

    블록이 많고 조건이 느슨한 언어는 후보가 급격히 늘어 리시브 한 번에 수 초~수 분이 걸린다.
    이 검사에 걸리면 조건을 좁히거나, 블록 수를 줄이거나, 스테이지의 max_serve를 낮춰주세요.
    """
    count = len(regular_candidate_words(stage.language, stage.max_serve))
    assert count <= MAX_RECEIVE_CANDIDATES, f"후보 w가 {count}개예요 (상한 {MAX_RECEIVE_CANDIDATES})."
