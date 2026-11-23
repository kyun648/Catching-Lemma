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
    "3. 정규 펌핑 게임": "pumping",
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
        f"NFA가 너무 커서 DFA로 바꿀 수 없어요. 바꾼 DFA의 상태가 {api.MAX_DFA_STATES}개를 넘어요. "
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
    stage = st.sidebar.selectbox("스테이지", stages, format_func=lambda s: f"{s['id']} · {s['title']}")
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
            st.graphviz_chart(api.diagram(machine, cex))
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
                st.graphviz_chart(api.diagram(dfa))


# ---------- 펌핑 게임 (탁구 4구 랠리) ----------

WIN_POINTS = 3  # 먼저 3포인트를 따면 이긴다

ROLES = {"깨는 쪽 (Lemma에 반박)": "break", "막는 쪽 (Lemma 편)": "defend"}

RULES = """
펌핑 보조정리를 **탁구 4구 랠리**로 진행해요. Lemma는 "L은 정규 언어"라고 주장해요.
**깨는 쪽**은 Lemma의 주장에 반박하고, **막는 쪽**은 Lemma 편에서 주장을 지켜요.

| 순서 | 하는 일 | 증명 문장 | 깨는 쪽일 때 | 막는 쪽일 때 |
|---|---|---|---|---|
| 1구 서브 | 펌핑 길이 $m$을 정해요 | 모든 $m$에 대해 | Lemma | 나 |
| 2구 리시브 | $w \\in L$, $|w| \\ge m$인 $w$를 골라요 | 어떤 $w$가 존재해서 | 나 | 컴퓨터 |
| 3구 수비 | $|xy| \\le m$, $|y| \\ge 1$인 분할 $w = xyz$를 골라요 | 모든 분할에 대해 | Lemma | 나 |
| 4구 스매시 | $xy^iz \\notin L$이 되는 $i$를 골라요 | 어떤 $i$가 존재해서 | 나 | 컴퓨터 |

- 스매시가 들어가면(= $xy^iz \\notin L$) 깨는 쪽, 막히면 막는 쪽이 득점해요. **먼저 3포인트**를 따면 이겨요.
- 컴퓨터는 보통 최선의 수를 두지만 가끔 실수해요. 실수는 1포인트 40%에서 시작해 포인트마다 줄어서 10%까지 내려가요.
- 깨는 쪽에서 진짜로 이기는 리시브는 **Lemma가 어떤 코스로 수비해도** 스매시가 들어가는 리시브예요.
- 막는 쪽에서 컴퓨터는 $i = 0, 2, 3, 4, 5$를 시험해요. 모두 L 안이면 막은 거예요.
- 깨는 쪽의 $w$는 블록 형태로 적어요: `a^m b^m`, `a^m b^(m+1)`, `a^(2m) b^m`. 지수에는 $m$과 정수, `+ - *`를 쓸 수 있어요.
- 이 언어가 정규 언어인지는 경기가 끝나면 알려줘요.
"""


def new_game(role: str) -> dict:
    return {
        "role": role,
        "score": [0, 0],  # [나, 상대]
        "point": 0,
        "phase": "receive" if role == "break" else "serve",
        "m": None,
        "template": "",
        "word": None,
        "split": None,  # {"start", "end", "x", "y", "z"}
        "smash": None,  # {"i", "pumped", "landed"}: landed는 스매시가 들어갔는지 (xyⁱz ∉ L)
        "computer_mode": None,  # 컴퓨터의 이번 수: "tough"/"random" (수비) 또는 "best"/"mistake" (리시브)
        "analysis": None,
        "best": None,
        "log": [],
    }


def mono(text: str) -> str:
    return f"`{text}`" if text else f"{LAMBDA}"


def opponent_name(role: str) -> str:
    return "Lemma" if role == "break" else "컴퓨터"


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

    left, right = ("Lemma (정규 언어라고 주장)", "나 (반박)") if role == "break" else ("나 (Lemma 편)", "컴퓨터 (반박)")
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


def split_html(split: dict) -> str:
    """x | y | z를 색으로 나눠 보여준다. y는 펌핑되는 구간."""
    def box(text: str, label: str, accent: bool) -> str:
        bg = "#FAECE7" if accent else "rgba(128,128,128,0.12)"
        fg = "#993C1D" if accent else "inherit"
        shown = text if text else LAMBDA
        return (f'<span style="display:inline-block; text-align:center; margin-right:4px;">'
                f'<span style="display:block; padding:4px 8px; border-radius:6px; background:{bg}; color:{fg}; '
                f'font-family:monospace; font-size:18px; letter-spacing:2px;">{shown}</span>'
                f'<span style="font-size:12px; opacity:0.7;">{label}</span></span>')

    return ('<div style="margin:6px 0 2px;">'
            + box(split["x"], "x", False) + box(split["y"], "y (펌핑 구간)", True) + box(split["z"], "z", False)
            + "</div>")


def shot_cards(game: dict) -> None:
    role, phase = game["role"], game["phase"]
    sp, sm = game["split"], game["smash"]
    owners = ["Lemma", "나", "Lemma", "나"] if role == "break" else ["나", "컴퓨터", "나", "컴퓨터"]
    serve = f"$m = {game['m']}$" if game["m"] is not None else "?"
    if game["word"] is None:
        receive = "?"
    elif role == "break":
        receive = f"{mono(game['template'])} → {mono(game['word'])}"
    else:
        receive = mono(game["word"])
    defense = f"x={mono(sp['x'])} · y={mono(sp['y'])} · z={mono(sp['z'])}" if sp and phase != "guard" else "?"
    if sm is None:
        smash = "?"
    elif sm["i"] is None:
        smash = "어떤 i도 안 통함"
    else:
        smash = f"$i = {sm['i']}$ → {mono(sm['pumped'])}"
    cards = [("1구 서브", serve, "∀m"), ("2구 리시브", receive, "∃w"),
             ("3구 수비", defense, "∀xyz"), ("4구 스매시", smash, "∃i")]
    for col, owner, (label, body, quantifier) in zip(st.columns(4), owners, cards):
        with col.container(border=True):
            st.caption(f"{label} · {owner} · {quantifier}")
            st.markdown(body)


def finish_point(game: dict, sid: str, landed: bool, i: int | None, pumped: str | None) -> None:
    """스매시 결과로 점수와 기록을 갱신하고 다음 단계로 넘긴다."""
    me_scored = landed if game["role"] == "break" else not landed
    game["score"][0 if me_scored else 1] += 1
    game["smash"] = {"i": i, "pumped": pumped, "landed": landed}
    game["analysis"] = api.pumping_analysis(sid, game["word"], game["m"])
    game["best"] = api.pumping_best_receive(sid, game["m"]) if game["role"] == "defend" else None
    sp = game["split"]
    game["log"].append({"포인트": game["point"] + 1, "m": game["m"], "w": game["word"], "x": sp["x"], "y": sp["y"],
                        "z": sp["z"], "i": "-" if i is None else str(i), "xyⁱz": pumped or "-",
                        "득점": "나" if me_scored else opponent_name(game["role"])})
    game["phase"] = "done" if max(game["score"]) >= WIN_POINTS else "result"


def next_point(game: dict, stage: dict) -> None:
    game.update(point=game["point"] + 1, word=None, split=None, smash=None, computer_mode=None,
                analysis=None, best=None)
    if game["role"] == "break":
        game.update(phase="receive", m=stage["m_values"][min(game["point"], len(stage["m_values"]) - 1)])
    else:
        game.update(phase="serve")


def play_break(game: dict, stage: dict, key: str) -> None:
    sid, m = stage["id"], game["m"]
    if game["phase"] == "receive":
        with st.form(f"{key}-receive"):
            template = st.text_input("2구 리시브: w를 고르세요", value=game["template"], placeholder="예: a^m b^m")
            submitted = st.form_submit_button("리시브", type="primary")
        if submitted:
            received = api.pumping_receive(sid, template, m)
            if not received["ok"]:
                st.error(f"폴트 — {received['error']}")
            else:
                defense = api.pumping_defend(sid, received["word"], m, seed=random.randrange(2**31),
                                             point=game["point"])
                if not defense["ok"]:
                    st.error(defense["error"])
                else:
                    split = {k: defense[k] for k in ("start", "end", "x", "y", "z")}
                    game.update(template=template, word=received["word"], computer_mode=defense["mode"],
                                split=split, phase="smash")
                    st.rerun()

    elif game["phase"] == "smash":
        sp = game["split"]
        st.markdown("**3구 수비** — Lemma가 이렇게 나눴어요.")
        st.html(split_html(sp))
        st.caption(f"|xy| = {len(sp['x'] + sp['y'])} ≤ m = {m},  |y| = {len(sp['y'])} ≥ 1")
        with st.form(f"{key}-smash"):
            i = st.radio("4구 스매시: i를 고르세요 (i = 1은 w 그대로라 뺐어요)", api.SMASH_VALUES, horizontal=True)
            submitted = st.form_submit_button("스매시", type="primary")
        if submitted:
            result = api.pumping_smash(sid, game["word"], m, sp["start"], sp["end"], i)
            if not result["ok"]:
                st.error(result["error"])
            else:
                finish_point(game, sid, landed=not result["in_language"], i=i, pumped=result["pumped"])
                st.rerun()


def play_defend(game: dict, stage: dict, key: str) -> None:
    sid = stage["id"]
    if game["phase"] == "serve":
        with st.form(f"{key}-serve"):
            m = st.number_input(f"1구 서브: 펌핑 길이 m을 고르세요 (1 ~ {api.MAX_SERVE})", min_value=1,
                                max_value=api.MAX_SERVE, value=game["m"] or 3, step=1)
            submitted = st.form_submit_button("서브", type="primary")
        if submitted:
            received = api.pumping_computer_receive(sid, int(m), point=game["point"], seed=random.randrange(2**31))
            if not received["ok"]:
                st.error(received["error"])
            else:
                game.update(m=int(m), word=received["word"], computer_mode=received["mode"], phase="guard")
                st.rerun()

    elif game["phase"] == "guard":
        word, m = game["word"], game["m"]
        st.markdown(f"**2구 리시브** — 컴퓨터가 $w$ = {mono(word)} 를 보냈어요. 이제 y를 골라 막으세요.")
        limit = min(m, len(word))
        start, end = st.slider(
            "3구 수비: y 구간을 고르세요 (두 손잡이 사이가 y, 0은 w의 맨 앞)",
            min_value=0, max_value=limit, value=(0, 1), step=1, key=f"{key}-guard-{game['point']}",
        )
        preview = {"start": start, "end": end, "x": word[:start], "y": word[start:end], "z": word[end:]}
        st.html(split_html(preview))
        st.caption(f"|xy| = {end} ≤ m = {m},  |y| = {end - start} ≥ 1")
        if st.button("수비", type="primary", key=f"{key}-guard-btn"):
            result = api.pumping_computer_smash(sid, word, m, start, end)
            if not result["ok"]:
                st.error(result["error"])
            else:
                game["split"] = preview
                finish_point(game, sid, landed=result["i"] is not None, i=result["i"], pumped=result["pumped"])
                st.rerun()


def pumping_chapter() -> None:
    stages = api.list_pumping_stages()
    stage = st.sidebar.selectbox("스테이지", stages, format_func=lambda s: f"{s['id']} · {s['title']}")
    role = ROLES[st.sidebar.radio("역할", list(ROLES))]
    sid = stage["id"]
    key = f"{sid}-{role}-game"
    if key not in st.session_state:
        game = new_game(role)
        if role == "break":
            game["m"] = stage["m_values"][0]
        st.session_state[key] = game
    game = st.session_state[key]

    st.subheader(stage["title"])
    st.markdown(f"$${stage['notation']}$$")
    st.write(stage["description"])
    with st.expander("규칙"):
        st.markdown(RULES)
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
    role, m = game["role"], game["m"]
    sp, sm, analysis = game["split"], game["smash"], game["analysis"]
    if not analysis["ok"]:
        st.error(f"수비 코스를 분석하지 못했어요. {analysis['error']}")
        return
    this_split = next(s for s in analysis["splits"] if s["start"] == sp["start"] and s["end"] == sp["end"])
    blockable = analysis["total"] - analysis["beaten"]

    if role == "break":
        if sm["landed"]:
            st.success(f"스매시 성공 — $xy^{{{sm['i']}}}z$ = {mono(sm['pumped'])} 는 L에 속하지 않아요. 득점!")
            if blockable:
                st.warning(f"행운의 득점이에요. Lemma가 최선이 아닌 코스로 수비했는데, 받아낼 수 있는 코스가 "
                           f"{blockable}개 있었어요. 아래 분석을 보고 리시브를 바꿔보세요.")
        else:
            st.error(f"Lemma가 받아냈어요 — $xy^{{{sm['i']}}}z$ = {mono(sm['pumped'])} 는 여전히 L 안이에요.")
            if this_split["breaking"]:
                st.caption(f"이 코스는 i = {', '.join(map(str, this_split['breaking']))}로 스매시했다면 뚫을 수 있었어요.")
            else:
                st.caption("이 코스는 어떤 i로도 뚫을 수 없어요. Lemma가 받아낼 코스가 있는 리시브라는 뜻이에요.")
    else:
        best = game["best"]
        if not sm["landed"]:
            st.success("수비 성공 — 컴퓨터가 i = 0, 2, 3, 4, 5 중 어떤 i로 쳐도 xyⁱz가 L 안이에요. 득점!")
        else:
            st.error(f"컴퓨터의 스매시 — $i = {sm['i']}$일 때 $xy^{{{sm['i']}}}z$ = {mono(sm['pumped'])} 는 L 밖이에요. 실점.")
            if blockable:
                st.caption(f"y를 다르게 잡았다면 막을 수 있었어요. 막히는 코스가 {blockable}개 있어요 (아래 분석).")
            else:
                st.caption("이 w는 어떤 y로도 막을 수 없는 리시브였어요.")
        if game["computer_mode"] == "mistake":
            st.caption("이번에 컴퓨터는 최선이 아닌 w를 골랐어요.")
        if not best["ok"]:
            pass
        elif best["winning_count"]:
            examples = ", ".join(mono(w) for w in best["winning_words"])
            st.caption(f"m = {m}에서 컴퓨터의 최선 리시브: {examples} 같은 w는 어떤 수비도 뚫어요.")
        else:
            st.caption(f"m = {m}에서는 컴퓨터가 어떤 w를 보내도 막을 코스가 있어요.")

    good = "막힘 (막는 쪽에 좋은 코스)" if role == "defend" else "없음 (막힘)"
    with st.expander(f"수비 코스 분석 (m = {m}): {analysis['total']}개 중 뚫리는 코스 {analysis['beaten']}개",
                     expanded=bool(blockable) and role == "break"):
        rows = [{"x": s["x"] or LAMBDA, "y": s["y"], "z": s["z"] or LAMBDA,
                 "통하는 i": ", ".join(map(str, s["breaking"])) or good} for s in analysis["splits"]]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("통하는 i가 없는 코스가 하나라도 있으면, 그 w로는 막는 쪽이 막을 수 있어요.")


def show_game_end(game: dict, sid: str) -> None:
    role = game["role"]
    me, opp = game["score"]
    regular = api.pumping_reveal(sid)["regular"]
    won = me >= WIN_POINTS
    kind = "**정규 언어예요.**" if regular else "**정규 언어가 아니에요.**"

    if role == "break":
        if won:
            st.success(f"스테이지 클리어 ({me} : {opp}) — Lemma의 주장을 반박했어요.")
        else:
            st.error(f"Lemma가 이겼어요 ({me} : {opp}).")
        if regular:
            st.info(f"이 언어는 {kind} m이 충분히 크면 Lemma는 언제나 막을 코스를 찾을 수 있어서, "
                    "펌핑 보조정리로는 반박할 수 없어요. 막는 쪽으로도 해보세요.")
        elif won:
            proof = api.pumping_proof(sid, game["template"])
            with st.container(border=True):
                st.markdown("**경기 기록지 → 증명문**")
                if proof["available"]:
                    st.markdown(proof["text"])
                else:
                    st.info(f"이번 리시브로는 증명문을 자동으로 쓸 수 없어요. {proof['reason']}")
        else:
            st.info(f"이 언어는 {kind} 어떤 수비도 뚫는 리시브가 있으니, 리시브(w)를 바꿔서 다시 도전해보세요.")
    else:
        if won:
            st.success(f"Lemma를 지켰어요 ({me} : {opp}).")
        else:
            st.error(f"컴퓨터가 이겼어요 ({me} : {opp}).")
        if regular:
            st.info(f"이 언어는 {kind} m을 충분히 크게 잡고 y를 잘 고르면 언제나 막을 수 있어요. "
                    "이게 펌핑 보조정리가 정규 언어에 대해 말하는 성질이에요. "
                    "다만 반대로, 펌핑 보조정리를 만족한다고 해서 정규 언어라는 증명이 되지는 않아요.")
        else:
            st.info(f"이 언어는 {kind} 컴퓨터가 최선으로 리시브하면 어떤 수비로도 막을 수 없어요. "
                    "이게 펌핑 보조정리로 정규 언어가 아님을 보이는 원리예요. 깨는 쪽으로 이기면 증명문을 볼 수 있어요.")
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
    elif chapter == "pumping":
        pumping_chapter()
    else:
        st.info("아직 준비 중인 챕터예요.")


if __name__ == "__main__":
    main()
