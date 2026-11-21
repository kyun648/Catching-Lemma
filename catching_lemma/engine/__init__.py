from __future__ import annotations

from .dfa import DFA, Issue, RunResult, find_counterexample, minimal_state_count
from .nfa import LAMBDA, NFA, NFARunResult


def automaton_from_dict(data: dict) -> DFA | NFA:
    """JSON의 "type" 값에 따라 DFA 또는 NFA를 만든다. type이 없으면 DFA로 본다."""
    if data.get("type") == "nfa":
        return NFA.from_dict(data)
    return DFA.from_dict(data)


__all__ = [
    "DFA",
    "NFA",
    "LAMBDA",
    "Issue",
    "RunResult",
    "NFARunResult",
    "automaton_from_dict",
    "find_counterexample",
    "minimal_state_count",
]
