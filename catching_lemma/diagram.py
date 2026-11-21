"""DFA를 Graphviz DOT 문자열로 바꾼다. Streamlit의 st.graphviz_chart가 브라우저에서 그려준다."""

from __future__ import annotations

from .engine import DFA


def _quote(name: str) -> str:
    return '"' + name.replace('"', '\\"') + '"'


def to_dot(dfa: DFA, highlight_path: list | None = None) -> str:
    """같은 두 상태 사이의 전이는 라벨을 합쳐서(a,b) 화살표 하나로 그린다.

    highlight_path: 반례를 실행했을 때 지나간 상태 목록. 해당 전이를 강조한다.
    """
    highlighted_edges = set()
    if highlight_path:
        for src, dst in zip(highlight_path, highlight_path[1:]):
            if src is not None and dst is not None:
                highlighted_edges.add((src, dst))

    lines = [
        "digraph DFA {",
        "  rankdir=LR;",
        '  bgcolor="transparent";',
        '  node [fontname="Helvetica", shape=circle];',
        '  edge [fontname="Helvetica"];',
        '  __start [shape=point, width=0];',
    ]
    for s in dfa.states:
        shape = "doublecircle" if s in dfa.accept else "circle"
        lines.append(f"  {_quote(s)} [shape={shape}];")
    if dfa.start in dfa.states:
        lines.append(f"  __start -> {_quote(dfa.start)};")

    merged: dict[tuple[str, str], list[str]] = {}
    for src, row in dfa.transitions.items():
        for sym, dst in row.items():
            if src in dfa.states and dst in dfa.states:
                merged.setdefault((src, dst), []).append(sym)

    for (src, dst), syms in merged.items():
        label = ",".join(sorted(syms))
        style = ', color="#D85A30", penwidth=2' if (src, dst) in highlighted_edges else ""
        lines.append(f'  {_quote(src)} -> {_quote(dst)} [label="{label}"{style}];')

    lines.append("}")
    return "\n".join(lines)
