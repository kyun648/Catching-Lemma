"""스테이지 정의(JSON) 불러오기와 채점."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .engine import DFA, NFA, automaton_from_dict, find_counterexample, minimal_state_count

STAGE_DIR = Path(__file__).parent / "stage_data"


@dataclass
class Stage:
    id: str
    chapter: str  # "dfa" 또는 "nfa"
    title: str
    description: str
    alphabet: list[str]
    reference: DFA | NFA  # 정답 기계. 같은 언어이기만 하면 어떤 모양이든 정답으로 인정한다.
    hint: str = ""
    # 설명에 쓴 예시 문자열. 테스트에서 정답 기계와 맞는지 확인한다.
    examples_accept: list[str] = field(default_factory=list)
    examples_reject: list[str] = field(default_factory=list)

    @property
    def reference_dfa(self) -> DFA:
        return to_dfa(self.reference)


@dataclass
class GradeResult:
    correct: bool
    counterexample: str | None = None
    expected: bool | None = None  # 반례를 정답 기계가 받아들이는지
    used_states: int | None = None  # 플레이어 설계의 상태 수 (DFA는 완전한 DFA 기준)
    optimal_states: int | None = None  # 같은 언어의 최소 DFA 상태 수 (완전한 DFA 기준)


def to_dfa(automaton: DFA | NFA) -> DFA:
    return automaton.to_dfa() if isinstance(automaton, NFA) else automaton


def load_stages(chapter: str | None = None) -> list[Stage]:
    stages = []
    for path in sorted(STAGE_DIR.glob("*/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if chapter and data["chapter"] != chapter:
            continue
        examples = data.get("examples", {})
        stages.append(
            Stage(
                id=data["id"],
                chapter=data["chapter"],
                title=data["title"],
                description=data["description"],
                alphabet=data["alphabet"],
                reference=automaton_from_dict(data["reference"]),
                hint=data.get("hint", ""),
                examples_accept=examples.get("accept", []),
                examples_reject=examples.get("reject", []),
            )
        )
    return stages


def grade(stage: Stage, candidate: DFA | NFA) -> GradeResult:
    """플레이어 설계를 정답 기계와 비교한다. 호출 전에 candidate.is_valid()를 확인할 것.

    NFA는 부분집합 구성으로 DFA로 바꾼 뒤 비교한다. 상태 수 비교는 DFA 챕터에서만 의미가 있다.
    """
    reference = stage.reference_dfa
    optimal = minimal_state_count(reference)
    cex = find_counterexample(to_dfa(candidate), reference)
    if cex is None:
        if isinstance(candidate, NFA):
            used = len(candidate.states)
        else:
            used = candidate.completed_state_count()
        return GradeResult(correct=True, used_states=used, optimal_states=optimal)
    return GradeResult(
        correct=False,
        counterexample=cex,
        expected=reference.accepts(cex),
        optimal_states=optimal,
    )
