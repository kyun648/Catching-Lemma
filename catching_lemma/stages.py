"""스테이지 정의(JSON) 불러오기와 채점."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .engine import DFA, find_counterexample, minimal_state_count

STAGE_DIR = Path(__file__).parent / "stage_data"


@dataclass
class Stage:
    id: str
    chapter: str
    title: str
    description: str
    alphabet: list[str]
    reference: DFA  # 정답 기계. 같은 언어이기만 하면 어떤 모양이든 정답으로 인정한다.
    hint: str = ""


@dataclass
class GradeResult:
    correct: bool
    counterexample: str | None = None
    expected: bool | None = None  # 반례를 정답 기계가 받아들이는지
    used_states: int | None = None  # 플레이어 설계의 상태 수 (완전한 DFA 기준)
    optimal_states: int | None = None  # 같은 언어의 최소 DFA 상태 수 (완전한 DFA 기준)


def load_stages(chapter: str | None = None) -> list[Stage]:
    stages = []
    for path in sorted(STAGE_DIR.glob("*/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if chapter and data["chapter"] != chapter:
            continue
        stages.append(
            Stage(
                id=data["id"],
                chapter=data["chapter"],
                title=data["title"],
                description=data["description"],
                alphabet=data["alphabet"],
                reference=DFA.from_dict(data["reference"]),
                hint=data.get("hint", ""),
            )
        )
    return stages


def grade(stage: Stage, candidate: DFA) -> GradeResult:
    """플레이어 설계를 정답 기계와 비교한다. 호출 전에 candidate.is_valid()를 확인할 것."""
    optimal = minimal_state_count(stage.reference)
    cex = find_counterexample(candidate, stage.reference)
    if cex is None:
        return GradeResult(
            correct=True,
            used_states=candidate.completed_state_count(),
            optimal_states=optimal,
        )
    return GradeResult(
        correct=False,
        counterexample=cex,
        expected=stage.reference.accepts(cex),
        optimal_states=optimal,
    )
