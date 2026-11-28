"""Catching Lemma Streamlit 앱. 실행: streamlit run app.py

화면은 catching_lemma.api만 쓰고, 엔진과는 오토마타 JSON(dict) 형식으로만 주고받는다.
"""

from __future__ import annotations

import random

import pandas as pd
import streamlit as st

from catching_lemma import api
from catching_lemma.api import LAMBDA

CHAPTERS = {
    "1. DFA": "dfa",
    "2. NFA": "nfa",
    "3. Pumping Rally": "pumping_game",
}


# ---------- 표시 도우미 ----------


def theme_type() -> str | None:
    """화면 테마("light" 또는 "dark"). 모르면 None이고, 그래프는 두 테마 모두에서 보이는 회색으로 그린다.

    Streamlit은 테마를 바꾼 직후나 처음 열 때 이전 값을 줄 수 있어서, 다음 화면 갱신 때 맞춰진다.
    """
    kind = st.context.theme.type
    return kind if kind in ("light", "dark") else None


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
        c1.selectbox("시작 상태", states, key=f"{key}-start-{len(states)}", filter_mode=None) if states else ""
    )
    accept = c2.multiselect("종료 상태", states, key=f"{key}-accept-{','.join(states)}")
    return states, start or "", accept


def build_dfa(stage: dict, key: str) -> dict:
    states, start, accept = state_inputs(key)
    alphabet = stage["alphabet"]
    st.caption("전이표: 각 칸에서 '그 상태에서 그 기호를 읽으면 갈 상태'를 골라요. 비워두면 거부로 처리해요.")
    table = pd.DataFrame("", index=states, columns=alphabet)
    edited = st.data_editor(
        table,
        key=f"{key}-table-{','.join(states)}",
        width="stretch",
        column_config={
            sym: st.column_config.SelectboxColumn(sym, options=states) for sym in alphabet
        },
    )
    transitions: dict[str, dict[str, str]] = {}
    for src in states:
        for sym in alphabet:
            dst = edited.at[src, sym]
            if isinstance(dst, str) and dst:
                transitions.setdefault(src, {})[sym] = dst
    return {"type": "dfa", "states": states, "alphabet": list(alphabet), "start": start,
            "accept": accept, "transitions": transitions}


def build_nfa(stage: dict, key: str) -> dict:
    states, start, accept = state_inputs(key)
    alphabet = stage["alphabet"]
    st.caption(
        "전이표: 각 칸에 갈 수 있는 상태를 쉼표로 모두 적어요 (예: `q0, q1`). "
        f"비워두면 그 경로는 사라져요. **{LAMBDA}** 칸은 글자를 읽지 않고 넘어가는 전이예요."
    )
    columns = list(alphabet) + [LAMBDA]
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
    return {"type": "nfa", "states": states, "alphabet": list(alphabet), "start": start,
            "accept": accept, "transitions": transitions}


# ---------- 결과 화면 ----------


def show_issues(machine: dict) -> None:
    for issue in api.validate(machine):
        (st.error if issue["level"] == "error" else st.warning)(issue["message"])


def trace_text(machine: dict, word: str) -> tuple[bool, str]:
    run = api.run(machine, word)
    if run["type"] == "nfa":
        return run["accepted"], f"활성 상태: {show_sets(run['trace'])}"
    return run["accepted"], f"지나간 상태: {show_path(run['trace'])}"


def too_large_message() -> str:
    return (
        f"NFA가 너무 커서 DFA로 바꿀 수 없어요. 바꾼 DFA의 상태가 {api.MAX_DFA_STATES:,}개를 넘어요. "
        "상태 수를 줄여보세요."
    )


def show_result(result: dict, machine: dict) -> None:
    if result["too_large"]:
        st.warning(too_large_message())
        return
    if result["correct"]:
        if machine["type"] == "nfa":
            st.success(f"정답이에요. NFA 상태 {result['used_states']}개")
            st.caption(
                f"같은 언어의 최소 DFA는 상태 {result['optimal_states']}개예요. "
                "다이어그램 아래 'DFA로 바꾸면'을 펼쳐서 비교해보세요."
            )
        else:
            st.success(f"정답이에요. 상태 {result['used_states']}개 (최소 {result['optimal_states']}개)")
            if result["used_states"] == result["optimal_states"]:
                st.caption("최소 상태 수로 풀었어요.")
            else:
                st.caption("같은 역할을 하는 상태를 합치면 더 줄일 수 있어요.")
        return
    cex = result["counterexample"]
    should = "받아들여야" if result["expected"] else "거부해야"
    did = "거부했어요" if result["expected"] else "받아들였어요"
    st.error(f"반례: {show_word(cex)} — {should} 하는데 {did}.")
    st.caption(trace_text(machine, cex)[1])


# ---------- 챕터 ----------


def stage_chapter(chapter: str) -> None:
    stages = api.list_stages(chapter)
    stage = st.sidebar.selectbox(
        "스테이지", stages, format_func=lambda s: f"{s['id']} · {s['title']}", filter_mode=None
    )
    key = stage["id"]
    result_key = f"{key}-result"

    st.subheader(stage["title"])
    st.write(stage["description"])
    if stage["hint"]:
        with st.expander("힌트"):
            st.write(stage["hint"])

    left, right = st.columns([1, 1])

    with left:
        machine = build_nfa(stage, key) if chapter == "nfa" else build_dfa(stage, key)
        show_issues(machine)
        can_grade = api.is_valid(machine)

        if st.button("채점하기", type="primary", key=f"{key}-grade"):
            if can_grade:
                st.session_state[result_key] = (api.normalize(machine), api.grade(key, machine))
            else:
                st.session_state.pop(result_key, None)
                st.error("위의 오류를 먼저 고쳐주세요.")

        # 채점 뒤에 설계를 고쳤다면 이전 결과는 보여주지 않는다.
        saved = st.session_state.get(result_key)
        result = saved[1] if saved and saved[0] == api.normalize(machine) else None
        if result is not None:
            show_result(result, machine)

        with st.expander("문자열 직접 실행해보기"):
            word = st.text_input("입력 문자열", key=f"{key}-try")
            if can_grade:
                accepted, trace = trace_text(machine, word)
                st.write(f"{show_word(word)}: **{'받아들임' if accepted else '거부'}**")
                st.caption(trace)

    with right:
        if machine["states"]:
            cex = result["counterexample"] if result is not None else None
            st.graphviz_chart(api.diagram(machine, cex, theme_type()))
            if chapter == "nfa":
                st.caption("겹원은 종료 상태, 칠해진 상태는 반례를 끝까지 읽은 뒤 남아 있는 상태예요.")
            else:
                st.caption("겹원은 종료 상태, 주황색 화살표는 반례를 실행한 경로예요.")

        if chapter == "nfa" and can_grade:
            with st.expander("DFA로 바꾸면 (부분집합 구성)"):
                dfa = api.to_dfa(machine)
                if dfa is None:
                    st.warning(too_large_message())
                    return
                st.caption(
                    f"NFA 상태들의 집합 하나하나가 DFA의 상태가 돼요. 도달 가능한 집합만 만들었더니 {len(dfa['states'])}개예요. "
                    "빈 집합(∅)으로 가는 전이는 그리지 않았어요."
                )
                st.graphviz_chart(api.diagram(dfa, theme=theme_type()))


# ---------- 펌핑 게임 (탁구 4구 랠리) ----------
#
# 정규 펌핑 게임(kind = "pumping", w = xyz)과 문맥자유 펌핑 게임(kind = "cfl_pumping", w = uvxyz)이
# 같은 화면을 쓴다. 분할 모양과 부르는 api만 다르다.

WIN_POINTS = 3  # 먼저 3포인트를 따면 이긴다

ROLES = {"깨는 쪽 (Lemma에 반박)": "break", "막는 쪽 (Lemma 편)": "defend"}

CLAIM = {"pumping": "정규 언어", "cfl_pumping": "문맥자유 언어"}
PARTS = {"pumping": ("x", "y", "z"), "cfl_pumping": ("u", "v", "x", "y", "z")}
PUMPED_PARTS = {"pumping": ("y",), "cfl_pumping": ("v", "y")}

# Pumping Rally 장(펌핑 게임): 공통 규칙을 먼저 보여주고, 그 아래에서 정규·문맥자유 게임을 고른다.
KINDS = {"정규 펌핑 게임 (w = xyz)": "pumping", "문맥자유 펌핑 게임 (w = uvxyz)": "cfl_pumping"}

COMMON_RULES = """
펌핑 보조정리를 **탁구 4구 랠리**로 진행해요.

**깨는 쪽**은 Lemma의 주장에 반박하고, **막는 쪽**은 Lemma 편에서 주장을 지켜요.

Lemma가 무엇을 주장하는지는 아래 게임별 규칙에 있어요.

| 순서 | 하는 일 | 증명 문장 | 깨는 쪽일 때 | 막는 쪽일 때 |
|---|---|---|---|---|
| 1구 서브 | 펌핑 길이 $m$을 정해요 | 모든 $m$에 대해 | Lemma | 나 |
| 2구 리시브 | $w \\in L$, $\\lvert w \\rvert \\ge m$인 $w$를 골라요 | 어떤 $w$가 존재해서 | 나 | 컴퓨터 |
| 3구 수비 | $w$를 조각으로 나눠요 (나누는 규칙은 게임마다 달라요) | 모든 분할에 대해 | Lemma | 나 |
| 4구 스매시 | 펌핑한 문자열이 $L$ 밖으로 나가는 $i$를 골라요 | 어떤 $i$가 존재해서 | 나 | 컴퓨터 |

**점수**
- 스매시가 들어가면(펌핑한 문자열 $\\notin L$) 깨는 쪽, 막히면 막는 쪽이 득점해요.
- **먼저 3포인트**를 따면 이겨요.

**컴퓨터**
- 컴퓨터는 최선의 수를 두지만, 처음 두 포인트에서는 가끔 실수해요 (1포인트 20%, 2포인트 10%).
- 3포인트부터는 실수하지 않아요. 그래서 컴퓨터의 실수만으로는 이길 수 없어요.
- 막는 쪽에서 컴퓨터는 $i = 0, 2, 3, 4, 5$를 시험해요. 모두 $L$ 안이면 막은 거예요.

**입력과 정답**
- 깨는 쪽의 $w$는 블록 형태로 적어요: `a^m b^m`, `a^(2m) b^m`, `a^(m*m)`.
- 지수에는 $m$과 정수, `+ - *`, 괄호를 쓸 수 있어요.
- 깨는 쪽에서 진짜로 이기는 리시브는 **Lemma가 어떤 코스로 수비해도** 스매시가 들어가는 리시브예요.
- 이 언어가 정규(문맥자유) 언어인지는 경기가 끝나면 알려줘요.
"""

KIND_RULES = {
    "pumping": """
**정규 펌핑 게임**: Lemma는 "L은 정규 언어"라고 주장해요.
- 3구 수비: $|xy| \\le m$, $|y| \\ge 1$인 분할 $w = xyz$. $y$는 $w$의 **앞쪽 $m$글자 안**에서만 골라요.
- 4구 스매시: $xy^iz \\notin L$이 되는 $i$를 골라요.
- 깨는 쪽으로 이기면 경기 기록으로 **증명문**을 정리해줘요.
""",
    "cfl_pumping": """
**문맥자유 펌핑 게임**: Lemma는 "L은 문맥자유 언어"라고 주장해요.
- 3구 수비: $|vxy| \\le m$, $|vy| \\ge 1$인 분할 $w = uvxyz$. $vxy$는 $w$의 앞쪽이 아니라 **어디에나** 올 수 있어요.
- 4구 스매시: $uv^ixy^iz \\notin L$이 되는 $i$를 골라요. $v$와 $y$를 **같은 횟수만큼 함께** 펌핑해요.
- 포인트가 끝나면 수비 코스를 **경우**($v$와 $y$가 각각 어느 글자 블록에 있는가)별로 묶은 표를 보여줘요.
- 교재의 경우 나누기 증명과 같은 방식이에요.
""",
}


def new_game(role: str, kind: str) -> dict:
    return {
        "kind": kind,
        "role": role,
        "score": [0, 0],  # [나, 상대]
        "point": 0,
        "phase": "receive" if role == "break" else "serve",
        "m": None,
        "template": "",
        "word": None,
        "split": None,  # 정규: {"start", "end", "x", "y", "z"}, 문맥자유: {"cuts", "u", "v", "x", "y", "z"}
        "smash": None,  # {"i", "pumped", "landed"}: landed는 스매시가 들어갔는지 (펌핑한 문자열 ∉ L)
        "computer_mode": None,  # 컴퓨터의 이번 수: "tough"/"random" (수비) 또는 "best"/"mistake" (리시브)
        "analysis": None,
        "best": None,
        "log": [],
    }


def mono(text: str) -> str:
    return f"`{text}`" if text else f"{LAMBDA}"


def opponent_name(role: str) -> str:
    return "Lemma" if role == "break" else "컴퓨터"


def pumped_name(kind: str, i) -> str:
    return f"xy^{{{i}}}z" if kind == "pumping" else f"uv^{{{i}}}xy^{{{i}}}z"


def split_key(split: dict, kind: str) -> tuple:
    return (split["start"], split["end"]) if kind == "pumping" else tuple(split["cuts"])


def scoreboard_html(game: dict, stage_title: str) -> str:
    me, opp = game["score"]
    m = game["m"] if game["m"] is not None else "?"
    return f"""
<div style="display:flex; justify-content:space-between; align-items:center; padding:6px 12px;
            border:1px solid rgba(128,128,128,0.3); border-radius:8px; font-size:14px;">
  <span>{stage_title}</span>
  <span style="font-size:22px; font-weight:600; font-family:monospace;">나 {me} : {opp} {opponent_name(game["role"])}</span>
  <span>포인트 {game["point"] + 1} · m = {m}</span>
</div>
"""


def shots_done(game: dict) -> int:
    return {"serve": 0, "receive": 1, "guard": 2, "smash": 3}.get(game["phase"], 4)


def table_svg(game: dict) -> str:
    """탁구대 SVG. 왼쪽이 Lemma 쪽, 오른쪽이 반박하는 쪽이다. 지금까지 친 공을 번호로 표시하고,
    마지막 공은 경로를 따라 날아간다.

    st.html은 SVG를 걸러내므로 st.image로 보여준다. 이미지 안에서는 화면 테마 색을 쓸 수 없어서
    글자는 밝은 테마와 어두운 테마 모두에서 보이는 회색으로 칠한다.
    """
    role, shots = game["role"], shots_done(game)
    finished = game["phase"] in ("result", "done")
    landed = finished and game["smash"]["landed"]

    points = [(130, 150), (430, 100), (230, 150), (510, 120)]
    paths = [
        "M130 150 Q240 40 430 100",
        "M430 100 Q340 20 230 150",
        "M230 150 Q330 60 510 120",
        "M510 120 Q400 150 170 105" if landed else "M510 120 Q420 40 250 140",
    ]
    colors = ["#888780", "#7F77DD", "#888780", "#D85A30"]
    parts = []
    for n in range(shots):
        dash = "" if n == shots - 1 else ' stroke-dasharray="3 3"'
        parts.append(f'<path id="shot{n}" d="{paths[n]}" fill="none" stroke="{colors[n]}" stroke-width="1.5"{dash}/>')
    for n in range(shots):
        x, y = points[n]
        parts.append(f'<circle cx="{x}" cy="{y}" r="11" fill="{colors[n]}" opacity="0.9"/>'
                     f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-family="sans-serif" font-size="12" '
                     f'fill="white">{n + 1}</text>')
    if shots:
        # 마지막 공이 경로를 따라 날아가는 애니메이션 (SVG 기본 기능이라 스크립트가 필요 없다)
        parts.append(f'<circle r="6" fill="#D85A30"><animateMotion dur="0.9s" fill="freeze">'
                     f'<mpath href="#shot{shots - 1}"/></animateMotion></circle>')

    caption = ""
    if finished:
        if role == "break":
            caption = "스매시가 수비를 뚫었어요 — 득점" if landed else "Lemma가 받아냈어요 — 실점"
        else:
            caption = "컴퓨터의 스매시가 뚫었어요 — 실점" if landed else "수비 성공 — 득점"

    claim = CLAIM[game["kind"]]
    left, right = (f"Lemma ({claim}라고 주장)", "나 (반박)") if role == "break" else ("나 (Lemma 편)", "컴퓨터 (반박)")
    label = 'font-family="sans-serif" font-size="13" fill="#888780"'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 30 680 182" width="680" height="182">
  <rect x="40" y="65" width="600" height="110" rx="4" fill="#E1F5EE" stroke="#0F6E56"/>
  <line x1="340" y1="55" x2="340" y2="185" stroke="#5F5E5A" stroke-width="3"/>
  <line x1="40" y1="120" x2="640" y2="120" stroke="#0F6E56" stroke-width="0.5" stroke-dasharray="4 4"/>
  <text x="50" y="50" {label}>{left}</text>
  <text x="630" y="50" {label} text-anchor="end">{right}</text>
  {"".join(parts)}
  <text x="340" y="203" {label} text-anchor="middle">{caption}</text>
</svg>"""


def split_html(split: dict, kind: str = "pumping") -> str:
    """분할 조각을 색으로 나눠 보여준다. 펌핑되는 조각(정규: y, 문맥자유: v와 y)은 강조한다."""
    def box(text: str, label: str, accent: bool) -> str:
        bg = "#FAECE7" if accent else "rgba(128,128,128,0.12)"
        fg = "#993C1D" if accent else "inherit"
        shown = text if text else LAMBDA
        return (f'<span style="display:inline-block; text-align:center; margin-right:4px;">'
                f'<span style="display:block; padding:4px 8px; border-radius:6px; background:{bg}; color:{fg}; '
                f'font-family:monospace; font-size:18px; letter-spacing:2px;">{shown}</span>'
                f'<span style="font-size:12px; opacity:0.7;">{label}</span></span>')

    pumped = PUMPED_PARTS[kind]
    boxes = [box(split[p], f"{p} (펌핑 구간)" if p in pumped else p, p in pumped) for p in PARTS[kind]]
    return '<div style="margin:6px 0 2px;">' + "".join(boxes) + "</div>"


def split_text(split: dict, kind: str) -> str:
    return " · ".join(f"{p}={mono(split[p])}" for p in PARTS[kind])


def shot_cards(game: dict) -> None:
    role, phase, kind = game["role"], game["phase"], game["kind"]
    sp, sm = game["split"], game["smash"]
    owners = ["Lemma", "나", "Lemma", "나"] if role == "break" else ["나", "컴퓨터", "나", "컴퓨터"]
    serve = f"$m = {game['m']}$" if game["m"] is not None else "?"
    if game["word"] is None:
        receive = "?"
    elif role == "break":
        receive = f"{mono(game['template'])} → {mono(game['word'])}"
    else:
        receive = mono(game["word"])
    defense = split_text(sp, kind) if sp and phase != "guard" else "?"
    if sm is None:
        smash = "?"
    elif sm["i"] is None:
        smash = "어떤 i도 안 통함"
    else:
        smash = f"$i = {sm['i']}$ → {mono(sm['pumped'])}"
    cards = [("1구 서브", serve, "∀m"), ("2구 리시브", receive, "∃w"),
             ("3구 수비", defense, "∀xyz" if kind == "pumping" else "∀uvxyz"), ("4구 스매시", smash, "∃i")]
    for col, owner, (label, body, quantifier) in zip(st.columns(4), owners, cards):
        with col.container(border=True):
            st.caption(f"{label} · {owner} · {quantifier}")
            st.markdown(body)


def finish_point(game: dict, sid: str, landed: bool, i: int | None, pumped: str | None) -> None:
    """스매시 결과로 점수와 기록을 갱신하고 다음 단계로 넘긴다."""
    kind = game["kind"]
    me_scored = landed if game["role"] == "break" else not landed
    game["score"][0 if me_scored else 1] += 1
    game["smash"] = {"i": i, "pumped": pumped, "landed": landed}
    if kind == "pumping":
        game["analysis"] = api.pumping_analysis(sid, game["word"], game["m"])
        best = api.pumping_best_receive
    else:
        game["analysis"] = api.cfl_analysis(sid, game["word"], game["m"], played=game["split"]["cuts"])
        best = api.cfl_best_receive
    game["best"] = best(sid, game["m"]) if game["role"] == "defend" else None
    sp = game["split"]
    row = {"포인트": game["point"] + 1, "m": game["m"], "w": game["word"]}
    row.update({p: sp[p] for p in PARTS[kind]})
    row.update({"i": "-" if i is None else str(i), "펌핑 결과": pumped or "-",
                "득점": "나" if me_scored else opponent_name(game["role"])})
    game["log"].append(row)
    game["phase"] = "done" if max(game["score"]) >= WIN_POINTS else "result"


def next_point(game: dict, stage: dict) -> None:
    game.update(point=game["point"] + 1, word=None, split=None, smash=None, computer_mode=None,
                analysis=None, best=None)
    if game["role"] == "break":
        game.update(phase="receive", m=stage["m_values"][min(game["point"], len(stage["m_values"]) - 1)])
    else:
        game.update(phase="serve")


def play_break(game: dict, stage: dict, key: str) -> None:
    sid, m, kind = stage["id"], game["m"], game["kind"]
    if game["phase"] == "receive":
        with st.form(f"{key}-receive"):
            example = "a^m b^m" if kind == "pumping" else "a^m b^m c^m"
            template = st.text_input("2구 리시브: w를 고르세요", value=game["template"], placeholder=f"예: {example}")
            submitted = st.form_submit_button("리시브", type="primary")
        if submitted:
            received = api.pumping_receive(sid, template, m)
            if not received["ok"]:
                st.error(f"폴트 — {received['error']}")
            else:
                seed = random.randrange(2**31)
                if kind == "pumping":
                    defense = api.pumping_defend(sid, received["word"], m, seed=seed, point=game["point"])
                    fields = ("start", "end", "x", "y", "z")
                else:
                    defense = api.cfl_defend(sid, received["word"], m, seed=seed, point=game["point"])
                    fields = ("cuts", "u", "v", "x", "y", "z")
                if not defense["ok"]:
                    st.error(defense["error"])
                else:
                    split = {k: defense[k] for k in fields}
                    game.update(template=template, word=received["word"], computer_mode=defense["mode"],
                                split=split, phase="smash")
                    st.rerun()

    elif game["phase"] == "smash":
        sp = game["split"]
        st.markdown("**3구 수비** — Lemma가 이렇게 나눴어요.")
        st.html(split_html(sp, kind))
        if kind == "pumping":
            st.caption(f"|xy| = {len(sp['x'] + sp['y'])} ≤ m = {m},  |y| = {len(sp['y'])} ≥ 1")
        else:
            st.caption(f"|vxy| = {len(sp['v'] + sp['x'] + sp['y'])} ≤ m = {m},  |vy| = {len(sp['v'] + sp['y'])} ≥ 1")
        with st.form(f"{key}-smash"):
            i = st.radio("4구 스매시: i를 고르세요 (i = 1은 w 그대로라 뺐어요)", api.SMASH_VALUES, horizontal=True)
            submitted = st.form_submit_button("스매시", type="primary")
        if submitted:
            if kind == "pumping":
                result = api.pumping_smash(sid, game["word"], m, sp["start"], sp["end"], i)
            else:
                result = api.cfl_smash(sid, game["word"], m, sp["cuts"], i)
            if not result["ok"]:
                st.error(result["error"])
            else:
                finish_point(game, sid, landed=not result["in_language"], i=i, pumped=result["pumped"])
                st.rerun()


def guard_regular(word: str, m: int, key: str) -> dict:
    limit = min(m, len(word))
    start, end = st.slider(
        "3구 수비: y 구간을 고르세요 (두 손잡이 사이가 y, 0은 w의 맨 앞)",
        min_value=0, max_value=limit, value=(0, 1), step=1, key=key,
    )
    preview = {"start": start, "end": end, "x": word[:start], "y": word[start:end], "z": word[end:]}
    st.html(split_html(preview))
    st.caption(f"|xy| = {end} ≤ m = {m},  |y| = {end - start} ≥ 1")
    return preview


def guard_cfl(word: str, m: int, key: str) -> dict | None:
    """문맥자유 수비 입력: 슬라이더 ①로 vxy 구간, 슬라이더 ②로 그 안의 x 구간을 고른다.
    vxy에서 x의 왼쪽이 v, 오른쪽이 y가 된다 (x가 vxy의 왼쪽 끝에 붙으면 v가 빈 문자열)."""
    n = len(word)
    p1, p4 = st.slider(
        f"3구 수비 ①: vxy 구간을 고르세요 (길이 m = {m} 이하, 0은 w의 맨 앞)",
        min_value=0, max_value=n, value=(0, min(m, n)), step=1, key=f"{key}-vxy",
    )
    if p4 - p1 < 1:
        st.info("vxy 구간이 비어 있어요. 한 글자 이상 고르세요.")
        return None
    mid = p1 + (p4 - p1) // 2
    p2, p3 = st.slider(
        "3구 수비 ②: 그 안에서 x 구간을 고르세요 (x의 왼쪽 나머지가 v, 오른쪽 나머지가 y)",
        min_value=p1, max_value=p4, value=(mid, mid), step=1, key=f"{key}-x-{p1}-{p4}",
    )
    preview = {"cuts": [p1, p2, p3, p4], "u": word[:p1], "v": word[p1:p2], "x": word[p2:p3],
               "y": word[p3:p4], "z": word[p4:]}
    st.html(split_html(preview, "cfl_pumping"))
    vxy_ok = "≤" if p4 - p1 <= m else "> (너무 길어요)"
    st.caption(f"|vxy| = {p4 - p1} {vxy_ok} m = {m},  |vy| = {(p2 - p1) + (p4 - p3)} ≥ 1")
    return preview


def play_defend(game: dict, stage: dict, key: str) -> None:
    sid, kind = stage["id"], game["kind"]
    max_serve = stage["max_serve"]
    if game["phase"] == "serve":
        with st.form(f"{key}-serve"):
            m = st.number_input(f"1구 서브: 펌핑 길이 m을 고르세요 (1 ~ {max_serve})", min_value=1,
                                max_value=max_serve, value=min(game["m"] or 3, max_serve), step=1)
            submitted = st.form_submit_button("서브", type="primary")
        if submitted:
            receive = api.pumping_computer_receive if kind == "pumping" else api.cfl_computer_receive
            with st.spinner("컴퓨터가 리시브를 고르는 중이에요…"):
                received = receive(sid, int(m), point=game["point"], seed=random.randrange(2**31))
            if not received["ok"]:
                st.error(received["error"])
            else:
                game.update(m=int(m), word=received["word"], computer_mode=received["mode"], phase="guard")
                st.rerun()

    elif game["phase"] == "guard":
        word, m = game["word"], game["m"]
        target = "y를" if kind == "pumping" else "v와 y를"
        st.markdown(f"**2구 리시브** — 컴퓨터가 $w$ = {mono(word)} 를 보냈어요. 이제 {target} 골라 막으세요.")
        slider_key = f"{key}-guard-{game['point']}"
        preview = guard_regular(word, m, slider_key) if kind == "pumping" else guard_cfl(word, m, slider_key)
        if st.button("수비", type="primary", key=f"{key}-guard-btn", disabled=preview is None):
            if kind == "pumping":
                result = api.pumping_computer_smash(sid, word, m, preview["start"], preview["end"])
            else:
                result = api.cfl_computer_smash(sid, word, m, preview["cuts"])
            if not result["ok"]:
                st.error(result["error"])
            else:
                game["split"] = preview
                finish_point(game, sid, landed=result["i"] is not None, i=result["i"], pumped=result["pumped"])
                st.rerun()


def pumping_chapter() -> None:
    """Pumping Rally 장(펌핑 게임). 본문 위쪽에 공통 규칙, 그 아래에 게임 종류(정규·문맥자유) 선택과 게임별 규칙을 둔다."""
    st.header("Pumping Rally")
    st.caption("펌핑 보조정리를 탁구 랠리로 겨루는 게임")
    with st.expander("공통 규칙 (처음이라면 먼저 읽어보세요)", expanded=True):
        st.markdown(COMMON_RULES)
    kind = KINDS[st.radio("게임", list(KINDS), horizontal=True, key="pumping-kind")]
    with st.container(border=True):
        st.markdown(KIND_RULES[kind])
    st.divider()

    stages = api.list_pumping_stages(kind)
    stage = st.sidebar.selectbox(
        "스테이지", stages, format_func=lambda s: f"{s['id']} · {s['title']}", filter_mode=None
    )
    role = ROLES[st.sidebar.radio("역할", list(ROLES))]
    sid = stage["id"]
    key = f"{sid}-{role}-game"
    if key not in st.session_state:
        game = new_game(role, kind)
        if role == "break":
            game["m"] = stage["m_values"][0]
        st.session_state[key] = game
    game = st.session_state[key]

    st.subheader(stage["title"])
    st.markdown(f"$${stage['notation']}$$")
    st.write(stage["description"])
    hint = stage["hint"] if role == "break" else stage["hint_defend"]
    if hint:
        with st.expander("힌트"):
            st.write(hint)

    st.html(scoreboard_html(game, stage["title"]))
    st.image(table_svg(game), width="stretch")
    shot_cards(game)

    if game["phase"] in ("result", "done"):
        show_point_result(game)
        if game["phase"] == "result":
            if st.button("다음 포인트", type="primary"):
                next_point(game, stage)
                st.rerun()
        else:
            show_game_end(game, sid)
            if st.button("다시 하기"):
                del st.session_state[key]
                st.rerun()
    elif role == "break":
        play_break(game, stage, key)
    else:
        play_defend(game, stage, key)


def show_point_result(game: dict) -> None:
    role, m, kind = game["role"], game["m"], game["kind"]
    sp, sm, analysis = game["split"], game["smash"], game["analysis"]
    if not analysis["ok"]:
        st.error(f"수비 코스를 분석하지 못했어요. {analysis['error']}")
        return
    if kind == "pumping":
        this_split = next(s for s in analysis["splits"] if split_key(s, kind) == split_key(sp, kind))
    else:  # 문맥자유: 분할이 수만 개라 api가 이번 분할을 따로 돌려준다
        this_split = analysis["played"]
    blockable = analysis["total"] - analysis["beaten"]
    target = "y" if kind == "pumping" else "v, y"

    if role == "break":
        if sm["landed"]:
            st.success(f"스매시 성공 — ${pumped_name(kind, sm['i'])}$ = {mono(sm['pumped'])} 는 L에 속하지 않아요. 득점!")
            if blockable:
                st.warning(f"행운의 득점이에요. Lemma가 최선이 아닌 코스로 수비했는데, 받아낼 수 있는 코스가 "
                           f"{blockable:,}개 있었어요. 아래 분석을 보고 리시브를 바꿔보세요.")
        else:
            st.error(f"Lemma가 받아냈어요 — ${pumped_name(kind, sm['i'])}$ = {mono(sm['pumped'])} 는 여전히 L 안이에요.")
            if this_split["breaking"]:
                st.caption(f"이 코스는 i = {', '.join(map(str, this_split['breaking']))}로 스매시했다면 뚫을 수 있었어요.")
            else:
                st.caption("이 코스는 어떤 i로도 뚫을 수 없어요. Lemma가 받아낼 코스가 있는 리시브라는 뜻이에요.")
    else:
        best = game["best"]
        if not sm["landed"]:
            st.success(f"수비 성공 — 컴퓨터가 i = 0, 2, 3, 4, 5 중 어떤 i로 쳐도 ${pumped_name(kind, 'i')}$가 L 안이에요. 득점!")
        else:
            st.error(f"컴퓨터의 스매시 — $i = {sm['i']}$일 때 ${pumped_name(kind, sm['i'])}$ = {mono(sm['pumped'])} 는 L 밖이에요. 실점.")
            if blockable:
                st.caption(f"{target}를 다르게 잡았다면 막을 수 있었어요. 막히는 코스가 {blockable:,}개 있어요 (아래 분석).")
            else:
                st.caption(f"이 w는 어떤 {target}로도 막을 수 없는 리시브였어요.")
        if game["computer_mode"] == "mistake":
            st.caption("이번에 컴퓨터는 최선이 아닌 w를 골랐어요.")
        if not best["ok"]:
            pass
        elif best["winning_count"]:
            examples = ", ".join(mono(w) for w in best["winning_words"])
            st.caption(f"m = {m}에서 컴퓨터의 최선 리시브: {examples} 같은 w는 어떤 수비도 뚫어요.")
        else:
            st.caption(f"m = {m}에서는 컴퓨터가 어떤 w를 보내도 막을 코스가 있어요.")

    if kind == "cfl_pumping":
        show_case_table(analysis, this_split["case"], role)

    good = "막힘 (막는 쪽에 좋은 코스)" if role == "defend" else "없음 (막힘)"
    expanded = bool(blockable) and role == "break" and kind == "pumping"
    with st.expander(f"수비 코스 분석 (m = {m}): {analysis['total']:,}개 중 뚫리는 코스 {analysis['beaten']:,}개",
                     expanded=expanded):
        rows = [{**{p: s[p] or LAMBDA for p in PARTS[kind]},
                 "통하는 i": ", ".join(map(str, s["breaking"])) or good} for s in analysis["splits"]]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if len(rows) < analysis["total"]:
            st.caption(f"총 {analysis['total']:,}개 중 처음 {len(rows)}개만 보여줘요 (막히는 코스부터). "
                       "전체는 위의 경우별 정리 표에서 경우마다 묶어서 볼 수 있어요.")
        st.caption("통하는 i가 없는 코스가 하나라도 있으면, 그 w로는 막는 쪽이 막을 수 있어요.")


def table_height(rows: int) -> int:
    """경우별 표가 스크롤 없이 모두 보이는 높이 (행 높이 35px + 머리글)."""
    return 35 * (rows + 1) + 3


def show_case_table(analysis: dict, current: int, role: str) -> None:
    """문맥자유 게임: 수비 코스를 경우(v, y가 어느 글자 블록에 있는가)별로 묶은 표. 이번 수비의 경우를 표시한다."""
    cases = analysis["cases"]
    open_cases = sum(1 for c in cases if c["blockable"])
    with st.expander(f"경우별 정리: {len(cases)}가지 경우 중 막히는 분할이 있는 경우 {open_cases}가지", expanded=True):
        rows = []
        for n, c in enumerate(cases):
            ex = c["example"]
            rows.append({
                "이번 수비": "◀" if n == current else "",
                "경우": f"{n + 1}. {c['label']}",
                "분할 수": c["total"],
                "막히는 분할": c["blockable"],
                "모든 분할에 통하는 i": ", ".join(map(str, c["common_i"])) or "-",
                "예 (u|v|x|y|z)": "|".join(ex[p] or LAMBDA for p in ("u", "v", "x", "y", "z")),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=table_height(len(rows)))
        if role == "break":
            st.caption("'막히는 분할'이 0인 경우만 남으면 Lemma가 어디에 수비해도 뚫을 수 있는 리시브예요. "
                       "'모든 분할에 통하는 i'가 '-'인 경우는 분할에 따라 다른 i가 필요해요.")
        else:
            st.caption("'막히는 분할'이 1 이상인 경우를 고르면 막을 수 있었어요. 예 칸은 그 경우의 대표 분할이에요 "
                       "(막히는 분할이 있으면 그중 하나).")


def show_case_report(sid: str, template: str, verdict: str) -> None:
    """깨는 쪽이 이긴 문맥자유 경기: 정답 안내 한 줄 + 경우별 정리 표.

    표를 만들 수 있는지 먼저 확인하고 안내 문구를 고른다 (만들 수 없으면 정답만 알리고 이유는 아래 상자에 맡긴다).
    """
    report = api.cfl_case_report(sid, template)
    if report["available"]:
        st.info(f"이 언어는 {verdict} 아래는 이번 경기 기록(리시브)으로 정리한 경우별 정리 표예요.")
    else:
        st.info(f"이 언어는 {verdict}")
    with st.container(border=True):
        st.markdown("**경기 기록지 → 경우별 정리**")
        if not report["available"]:
            st.info(f"이번 리시브로는 경우별 정리를 만들 수 없어요. {report['reason']}")
            return
        lo, hi = min(report["checked_m"]), max(report["checked_m"])
        st.markdown(f"$w$ = {mono(template)} 로 리시브하면, $|vxy| \\le m$, $|vy| \\ge 1$인 모든 분할이 "
                    f"아래 {len(report['rows'])}가지 경우 중 하나에 속해요. **이 경우 목록은 모든 m에서 같아요** "
                    "(블록이 모두 m글자 이상이라 vxy는 이웃한 두 블록까지만 걸쳐요).")
        rows = [{"경우": f"{n + 1}. {r['label']}",
                 "통하는 i": ", ".join(map(str, r["smash"])),
                 f"예 (m = {r['example_m']}, u|v|x|y|z)": "|".join(r["example"][p] or LAMBDA
                                                               for p in ("u", "v", "x", "y", "z"))}
                for n, r in enumerate(report["rows"])]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=table_height(len(rows)))
        # 경우 목록은 모든 m에서 성립하지만(엔진이 식으로 확인), w ∈ L과 각 경우의 i는 m = lo~hi에서만 확인한 결과다.
        # 그래서 확인 범위를 먼저 밝히고, 교재 형식의 증명으로 옮길 때 학생이 직접 보여야 할 두 가지를 적는다.
        first = report["rows"][0]
        st.markdown(
            f"**m = {lo}~{hi}에서는** 모든 경우에 L 밖으로 보내는 $i$가 있었어요. "
            "이 표를 교재 형식의 증명으로 옮기려면 두 가지를 모든 m에 대해 직접 보여야 해요.\n\n"
            f"1. **$w \\in L$**: 모든 m에서 {mono(template)} 가 L에 속한다는 것\n"
            f"2. **각 경우의 $i$로 펌핑한 문자열이 L 밖이다**: 예를 들어 1번 경우({first['label']})에서 "
            f"$i = {first['smash'][0]}$로 펌핑한 문자열이 L의 조건을 만족하지 않는다는 것\n\n"
            "이 둘을 보이면 펌핑 보조정리에 모순이므로 L은 문맥자유 언어가 아니라는 증명이 돼요."
        )


def show_game_end(game: dict, sid: str) -> None:
    role, kind = game["role"], game["kind"]
    me, opp = game["score"]
    if kind == "pumping":
        pumpable = api.pumping_reveal(sid)["regular"]
    else:
        pumpable = api.cfl_reveal(sid)["context_free"]
    claim = CLAIM[kind]
    won = me >= WIN_POINTS
    verdict = f"**{claim}예요.**" if pumpable else f"**{claim}가 아니에요.**"

    if role == "break":
        if won:
            st.success(f"스테이지 클리어 ({me} : {opp}) — Lemma의 주장을 반박했어요.")
        else:
            st.error(f"Lemma가 이겼어요 ({me} : {opp}).")
        if pumpable:
            st.info(f"이 언어는 {verdict} m이 충분히 크면 Lemma는 언제나 막을 코스를 찾을 수 있어서, "
                    "펌핑 보조정리로는 반박할 수 없어요. 막는 쪽으로도 해보세요.")
        elif won and kind == "pumping":
            # 증명문을 만들 수 있는지 먼저 확인하고 안내 문구를 고른다 (만들 수 없으면 이유는 아래 상자에 맡긴다)
            proof = api.pumping_proof(sid, game["template"])
            if proof["available"]:
                st.info(f"이 언어는 {verdict} 아래는 이번 경기 기록(리시브)으로 정리한 증명문이에요.")
            else:
                st.info(f"이 언어는 {verdict}")
            with st.container(border=True):
                st.markdown("**경기 기록지 → 증명문**")
                if proof["available"]:
                    st.markdown(proof["text"])
                else:
                    st.info(f"이번 리시브로는 증명문을 자동으로 쓸 수 없어요. {proof['reason']}")
        elif won:
            show_case_report(sid, game["template"], verdict)
        else:
            st.info(f"이 언어는 {verdict} 어떤 수비도 뚫는 리시브가 있으니, 리시브(w)를 바꿔서 다시 도전해보세요.")
    else:
        if won:
            st.success(f"Lemma를 지켰어요 ({me} : {opp}).")
        else:
            st.error(f"컴퓨터가 이겼어요 ({me} : {opp}).")
        if pumpable:
            st.info(f"이 언어는 {verdict} m을 충분히 크게 잡고 분할을 잘 고르면 언제나 막을 수 있어요. "
                    f"이게 펌핑 보조정리가 {claim}에 대해 말하는 성질이에요. "
                    f"다만 반대로, 펌핑 보조정리를 만족한다고 해서 {claim}라는 증명이 되지는 않아요.")
        else:
            st.info(f"이 언어는 {verdict} 컴퓨터가 최선으로 리시브하면 어떤 수비로도 막을 수 없어요. "
                    f"이게 펌핑 보조정리로 {claim}가 아님을 보이는 원리예요. 깨는 쪽으로 이기면 "
                    + ("증명문을" if kind == "pumping" else "경우별 정리 표를") + " 볼 수 있어요.")
        st.caption("컴퓨터는 i = 0, 2, 3, 4, 5만 시험해요. '막았다'는 판정은 이 범위 안에서의 확인이에요.")
    with st.expander("경기 기록"):
        st.dataframe(pd.DataFrame(game["log"]), hide_index=True, width="stretch")


def main() -> None:
    st.set_page_config(page_title="Catching Lemma", layout="wide")
    st.sidebar.title("Catching Lemma")
    st.sidebar.caption("만들고, 틀리고, 증명하는 오토마타 퍼즐")
    chapter = CHAPTERS[st.sidebar.radio("챕터", list(CHAPTERS))]

    if chapter in ("dfa", "nfa"):
        stage_chapter(chapter)
    elif chapter == "pumping_game":
        pumping_chapter()
    else:
        st.info("아직 준비 중인 챕터예요.")


if __name__ == "__main__":
    main()
