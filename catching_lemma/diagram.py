"""DFA·NFA를 Graphviz DOT 문자열로 바꾼다. Streamlit의 st.graphviz_chart가 브라우저에서 그려준다."""

from __future__ import annotations

from .engine import DFA, LAMBDA, NFA

HIGHLIGHT = "#D85A30"
# 글자·테두리·화살표 색. 배경은 투명하므로 화면 테마에 맞춘다.
# 테마를 모를 때(None)는 밝은 테마와 어두운 테마 모두에서 보이는 회색을 쓴다 (탁구대 그림과 같은 색).
FOREGROUND = {"light": "#31333F", "dark": "#E6E6E6", None: "#888780"}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '\\"') + '"'


def _edges(automaton: DFA | NFA):
    """(출발, 기호, 도착) 목록. DFA는 도착이 하나, NFA는 목록이다."""
    for src, row in automaton.transitions.items():
        for sym, dst in row.items():
            for d in dst if isinstance(dst, list) else [dst]:
                yield src, sym, d


def to_dot(
    automaton: DFA | NFA,
    highlight_path: list | None = None,
    highlight_states: set | frozenset | None = None,
    theme: str | None = None,
) -> str:
    """같은 두 상태 사이의 전이는 라벨을 합쳐서(a,b) 화살표 하나로 그린다.

    highlight_path: DFA 반례를 실행했을 때 지나간 상태 목록. 해당 전이를 강조한다.
    highlight_states: NFA 반례를 끝까지 읽은 뒤 활성화된 상태들. 해당 상태를 칠한다.
    theme: 화면 테마("light" 또는 "dark"). 그 밖의 값이나 None이면 두 테마 모두에서 보이는 회색으로 그린다.
    """
    fg = FOREGROUND.get(theme, FOREGROUND[None])
    highlighted_edges = set()
    if highlight_path:
        for src, dst in zip(highlight_path, highlight_path[1:]):
            if src is not None and dst is not None:
                highlighted_edges.add((src, dst))
    highlight_states = highlight_states or set()

    lines = [
        "digraph automaton {",
        "  rankdir=LR;",
        '  bgcolor="transparent";',
        f'  node [fontname="Helvetica", shape=circle, color="{fg}", fontcolor="{fg}"];',
        f'  edge [fontname="Helvetica", color="{fg}", fontcolor="{fg}"];',
        "  __start [shape=point, width=0];",
    ]
    for s in automaton.states:
        shape = "doublecircle" if s in automaton.accept else "circle"
        style = f', style=filled, fillcolor="{HIGHLIGHT}", fontcolor=white' if s in highlight_states else ""
        lines.append(f"  {_quote(s)} [shape={shape}{style}];")
    if automaton.start in automaton.states:
        lines.append(f"  __start -> {_quote(automaton.start)};")

    merged: dict[tuple[str, str], list[str]] = {}
    for src, sym, dst in _edges(automaton):
        if src in automaton.states and dst in automaton.states:
            merged.setdefault((src, dst), []).append(sym)

    for (src, dst), syms in merged.items():
        # λ는 맨 뒤에 표시
        label = ",".join(sorted(syms, key=lambda s: (s == LAMBDA, s)))
        style = f', color="{HIGHLIGHT}", penwidth=2' if (src, dst) in highlighted_edges else ""
        lines.append(f'  {_quote(src)} -> {_quote(dst)} [label="{label}"{style}];')

    lines.append("}")
    return "\n".join(lines)
