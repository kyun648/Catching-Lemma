"""Catching Lemma Streamlit 앱. 실행: streamlit run app.py"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from catching_lemma.diagram import to_dot
from catching_lemma.engine import DFA, LAMBDA, NFA
from catching_lemma.stages import Stage, grade, load_stages

CHAPTERS = {
    "1. DFA": "dfa",
    "2. NFA": "nfa",
    "3. 정규 펌핑 게임 (준비 중)": None,
    "4. 문맥자유 펌핑 게임 (준비 중)": None,
}


# ---------- 표시 도우미 ----------


def show_word(word: str) -> str:
    return f"{LAMBDA} (빈 문자열)" if word == "" else f"`{word}`"


def show_path(path: list) -> str:
    """DFA 실행 경로: q0 → q1 → (전이 없음)"""
    return " → ".join("(전이 없음)" if s is None else str(s) for s in path)


def show_sets(steps: list) -> str:
    """NFA 실행 경로: {q0} → {q0,q1} → ∅"""
    return " → ".join("{" + ",".join(sorted(s)) + "}" if s else "∅" for s in steps)


def parse_names(text: str) -> list[str]:
    """쉼표로 구분한 이름 목록. 빈칸과 중복은 제거한다."""
    seen, names = set(), []
    for name in (part.strip() for part in str(text).split(",")):
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


# ---------- 입력 화면: 위젯 값 → 오토마타 JSON 형식 ----------


def state_inputs(key: str) -> tuple[list[str], str, list[str]]:
    states = parse_names(
        st.text_input("상태 이름 (쉼표로 구분)", value="q0, q1", key=f"{key}-states")
    )
    c1, c2 = st.columns(2)
    start = (
        c1.selectbox("시작 상태", states, key=f"{key}-start-{len(states)}") if states else ""
    )
    accept = c2.multiselect("종료 상태", states, key=f"{key}-accept-{','.join(states)}")
    return states, start or "", accept


def build_dfa(stage: Stage, key: str) -> DFA:
    states, start, accept = state_inputs(key)
    st.caption("전이표: 각 칸에서 '그 상태에서 그 기호를 읽으면 갈 상태'를 골라요. 비워두면 거부로 처리해요.")
    table = pd.DataFrame("", index=states, columns=stage.alphabet)
    edited = st.data_editor(
        table,
        key=f"{key}-table-{','.join(states)}",
        width="stretch",
        column_config={
            sym: st.column_config.SelectboxColumn(sym, options=states) for sym in stage.alphabet
        },
    )
    transitions: dict[str, dict[str, str]] = {}
    for src in states:
        for sym in stage.alphabet:
            dst = edited.at[src, sym]
            if isinstance(dst, str) and dst:
                transitions.setdefault(src, {})[sym] = dst
    return DFA(states=states, alphabet=list(stage.alphabet), start=start,
               accept=set(accept), transitions=transitions)


def build_nfa(stage: Stage, key: str) -> NFA:
    states, start, accept = state_inputs(key)
    st.caption(
        "전이표: 각 칸에 갈 수 있는 상태를 쉼표로 모두 적어요 (예: `q0, q1`). "
        f"비워두면 그 경로는 사라져요. **{LAMBDA}** 칸은 글자를 읽지 않고 넘어가는 전이예요."
    )
    columns = list(stage.alphabet) + [LAMBDA]
    table = pd.DataFrame("", index=states, columns=columns)
    edited = st.data_editor(
        table,
        key=f"{key}-table-{','.join(states)}",
        width="stretch",
        column_config={sym: st.column_config.TextColumn(sym) for sym in columns},
    )
    transitions: dict[str, dict[str, list[str]]] = {}
    for src in states:
        for sym in columns:
            # 지운 칸은 ""가 아니라 NaN/None으로 올 수 있어서 문자열일 때만 읽는다.
            cell = edited.at[src, sym]
            dsts = parse_names(cell) if isinstance(cell, str) else []
            if dsts:
                transitions.setdefault(src, {})[sym] = dsts
    return NFA(states=states, alphabet=list(stage.alphabet), start=start,
               accept=set(accept), transitions=transitions)


# ---------- 결과 화면 ----------


def show_issues(candidate: DFA | NFA) -> None:
    for issue in candidate.validate():
        (st.error if issue.level == "error" else st.warning)(issue.message)


def trace_text(candidate: DFA | NFA, word: str) -> tuple[bool, str]:
    run = candidate.run(word)
    if isinstance(candidate, NFA):
        return run.accepted, f"활성 상태: {show_sets(run.steps)}"
    return run.accepted, f"지나간 상태: {show_path(run.path)}"


def show_result(result, candidate: DFA | NFA) -> None:
    if result.correct:
        if isinstance(candidate, NFA):
            st.success(f"정답이에요. NFA 상태 {result.used_states}개")
            st.caption(
                f"같은 언어의 최소 DFA는 상태 {result.optimal_states}개예요. "
                "다이어그램 아래 'DFA로 바꾸면'을 펼쳐서 비교해보세요."
            )
        else:
            st.success(f"정답이에요. 상태 {result.used_states}개 (최소 {result.optimal_states}개)")
            if result.used_states == result.optimal_states:
                st.caption("최소 상태 수로 풀었어요.")
            else:
                st.caption("같은 역할을 하는 상태를 합치면 더 줄일 수 있어요.")
        return
    cex = result.counterexample
    should = "받아들여야" if result.expected else "거부해야"
    did = "거부했어요" if result.expected else "받아들였어요"
    st.error(f"반례: {show_word(cex)} — {should} 하는데 {did}.")
    st.caption(trace_text(candidate, cex)[1])


def highlight_for(result, candidate: DFA | NFA) -> dict:
    if result is None or result.correct:
        return {}
    run = candidate.run(result.counterexample)
    if isinstance(candidate, NFA):
        return {"highlight_states": run.steps[-1]}
    return {"highlight_path": run.path}


# ---------- 챕터 ----------


def stage_chapter(chapter: str) -> None:
    stages = load_stages(chapter)
    stage = st.sidebar.selectbox("스테이지", stages, format_func=lambda s: f"{s.id} · {s.title}")
    key = stage.id
    result_key = f"{key}-result"

    st.subheader(stage.title)
    st.write(stage.description)
    if stage.hint:
        with st.expander("힌트"):
            st.write(stage.hint)

    left, right = st.columns([1, 1])

    with left:
        candidate = build_nfa(stage, key) if chapter == "nfa" else build_dfa(stage, key)
        show_issues(candidate)
        can_grade = candidate.is_valid()

        if st.button("채점하기", type="primary", key=f"{key}-grade"):
            if can_grade:
                st.session_state[result_key] = (candidate.to_dict(), grade(stage, candidate))
            else:
                st.session_state.pop(result_key, None)
                st.error("위의 오류를 먼저 고쳐주세요.")

        # 채점 뒤에 설계를 고쳤다면 이전 결과는 보여주지 않는다.
        saved = st.session_state.get(result_key)
        result = saved[1] if saved and saved[0] == candidate.to_dict() else None
        if result is not None:
            show_result(result, candidate)

        with st.expander("문자열 직접 실행해보기"):
            word = st.text_input("입력 문자열", key=f"{key}-try")
            if can_grade:
                accepted, trace = trace_text(candidate, word)
                st.write(f"{show_word(word)}: **{'받아들임' if accepted else '거부'}**")
                st.caption(trace)

    with right:
        if candidate.states:
            st.graphviz_chart(to_dot(candidate, **highlight_for(result, candidate)))
            if chapter == "nfa":
                st.caption("겹원은 종료 상태, 칠해진 상태는 반례를 끝까지 읽은 뒤 남아 있는 상태예요.")
            else:
                st.caption("겹원은 종료 상태, 주황색 화살표는 반례를 실행한 경로예요.")

        if chapter == "nfa" and can_grade:
            with st.expander("DFA로 바꾸면 (부분집합 구성)"):
                dfa = candidate.to_dfa()
                st.caption(
                    f"NFA 상태들의 집합 하나하나가 DFA의 상태가 돼요. 도달 가능한 집합만 만들었더니 {len(dfa.states)}개예요. "
                    "빈 집합(∅)으로 가는 전이는 그리지 않았어요."
                )
                st.graphviz_chart(to_dot(dfa))


def main() -> None:
    st.set_page_config(page_title="Catching Lemma", layout="wide")
    st.sidebar.title("Catching Lemma")
    st.sidebar.caption("만들고, 틀리고, 증명하는 오토마타 퍼즐")
    chapter = CHAPTERS[st.sidebar.radio("챕터", list(CHAPTERS))]

    if chapter in ("dfa", "nfa"):
        stage_chapter(chapter)
    else:
        st.info("아직 준비 중인 챕터예요.")


if __name__ == "__main__":
    main()
