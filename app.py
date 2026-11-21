"""Catching Lemma Streamlit 앱. 실행: streamlit run app.py"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from catching_lemma.diagram import to_dot
from catching_lemma.engine import DFA
from catching_lemma.stages import Stage, grade, load_stages

CHAPTERS = {
    "1. DFA": "dfa",
    "2. NFA (준비 중)": None,
    "3. 정규 펌핑 게임 (준비 중)": None,
    "4. 문맥자유 펌핑 게임 (준비 중)": None,
}


def show_word(word: str) -> str:
    return "ε (빈 문자열)" if word == "" else f"`{word}`"


def show_path(path: list) -> str:
    return " → ".join("(전이 없음)" if s is None else str(s) for s in path)


def parse_states(text: str) -> list[str]:
    seen, states = set(), []
    for name in (part.strip() for part in text.split(",")):
        if name and name not in seen:
            seen.add(name)
            states.append(name)
    return states


def build_dfa(stage: Stage, key: str) -> DFA:
    """입력 위젯에서 DFA 데이터를 만든다. 입력 방식이 바뀌어도 여기서 나오는 형식은 같다."""
    states_text = st.text_input(
        "상태 이름 (쉼표로 구분)", value="q0, q1", key=f"{key}-states"
    )
    states = parse_states(states_text)

    c1, c2 = st.columns(2)
    start = c1.selectbox("시작 상태", states, key=f"{key}-start-{len(states)}") if states else ""
    accept = c2.multiselect("종료 상태", states, key=f"{key}-accept-{','.join(states)}")

    st.caption("전이표: 각 칸에 '그 상태에서 그 기호를 읽으면 갈 상태'를 골라요. 비워두면 거부로 처리해요.")
    table = pd.DataFrame("", index=states, columns=stage.alphabet)
    edited = st.data_editor(
        table,
        key=f"{key}-table-{','.join(states)}",
        width="stretch",
        column_config={
            sym: st.column_config.SelectboxColumn(sym, options=states)
            for sym in stage.alphabet
        },
    )

    transitions: dict[str, dict[str, str]] = {}
    for src in states:
        for sym in stage.alphabet:
            dst = edited.at[src, sym]
            if isinstance(dst, str) and dst:
                transitions.setdefault(src, {})[sym] = dst

    return DFA(
        states=states,
        alphabet=list(stage.alphabet),
        start=start or "",
        accept=set(accept),
        transitions=transitions,
    )


def dfa_chapter() -> None:
    stages = load_stages("dfa")
    stage = st.sidebar.selectbox(
        "스테이지", stages, format_func=lambda s: f"{s.id} · {s.title}"
    )
    key = stage.id
    result_key = f"{key}-result"

    st.subheader(stage.title)
    st.write(stage.description)
    if stage.hint:
        with st.expander("힌트"):
            st.write(stage.hint)

    left, right = st.columns([1, 1])

    with left:
        candidate = build_dfa(stage, key)
        issues = candidate.validate()
        for issue in issues:
            (st.error if issue.level == "error" else st.warning)(issue.message)

        can_grade = candidate.is_valid()
        if st.button("채점하기", type="primary", key=f"{key}-grade"):
            if can_grade:
                st.session_state[result_key] = (candidate.to_dict(), grade(stage, candidate))
            else:
                st.session_state.pop(result_key, None)
                st.error("위의 오류를 먼저 고쳐주세요.")

        saved = st.session_state.get(result_key)
        result = saved[1] if saved and saved[0] == candidate.to_dict() else None

        if result is not None:
            if result.correct:
                msg = f"정답이에요. 상태 {result.used_states}개 (최소 {result.optimal_states}개)"
                st.success(msg)
                if result.used_states == result.optimal_states:
                    st.caption("최소 상태 수로 풀었어요.")
                else:
                    st.caption("같은 역할을 하는 상태를 합치면 더 줄일 수 있어요.")
            else:
                cex = result.counterexample
                should = "받아들여야" if result.expected else "거부해야"
                did = "거부했어요" if result.expected else "받아들였어요"
                run = candidate.run(cex)
                st.error(f"반례: {show_word(cex)} — {should} 하는데 {did}.")
                st.caption(f"지나간 상태: {show_path(run.path)}")

        with st.expander("문자열 직접 실행해보기"):
            word = st.text_input("입력 문자열", key=f"{key}-try")
            if can_grade:
                run = candidate.run(word)
                verdict = "받아들임" if run.accepted else "거부"
                st.write(f"{show_word(word)}: **{verdict}**")
                st.caption(f"지나간 상태: {show_path(run.path)}")

    with right:
        highlight = None
        if result is not None and not result.correct:
            highlight = candidate.run(result.counterexample).path
        if candidate.states:
            st.graphviz_chart(to_dot(candidate, highlight))
            st.caption("겹원은 종료 상태, 주황색 화살표는 반례를 실행한 경로예요.")


def main() -> None:
    st.set_page_config(page_title="Catching Lemma", layout="wide")
    st.sidebar.title("Catching Lemma")
    st.sidebar.caption("만들고, 틀리고, 증명하는 오토마타 퍼즐")
    chapter_label = st.sidebar.radio("챕터", list(CHAPTERS))
    chapter = CHAPTERS[chapter_label]

    if chapter == "dfa":
        dfa_chapter()
    else:
        st.info("아직 준비 중인 챕터예요.")


if __name__ == "__main__":
    main()
