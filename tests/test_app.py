"""화면(app.py) 동작 검사. Streamlit AppTest로 브라우저 없이 화면을 실행하고 버튼·입력을 조작한다.

DFA·NFA 장은 채점까지, 두 펌핑 게임은 두 역할로 경기가 끝날 때까지 진행한다.
경기 결과가 매번 같도록, 이기는 수가 정해진 스테이지와 수만 고른다
(컴퓨터의 실수는 무작위지만, 아래 수는 컴퓨터가 어떻게 두든 결과가 같다).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from catching_lemma import api

APP = str(Path(__file__).resolve().parent.parent / "app.py")
BREAK = "깨는 쪽 (Lemma에 반박)"
DEFEND = "막는 쪽 (Lemma 편)"
MAX_POINTS = 5  # 3포인트 선승이라 경기는 길어야 5포인트


def open_chapter(chapter: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    at.sidebar.radio[0].set_value(chapter).run()
    assert not at.exception, at.exception
    return at


PUMPING_CHAPTERS = {"3. 정규 펌핑 게임": "pumping", "4. 문맥자유 펌핑 게임": "cfl_pumping"}


def open_game(chapter: str, stage_id: str, role: str) -> AppTest:
    at = open_chapter(chapter)
    # 선택 상자에는 화면과 같은 원래 스테이지 dict를 넘긴다. 표시 문자열("pump-01 · ...")을 넘기면
    # 일부 Streamlit 버전의 AppTest가 format_func(문자열)을 불러 TypeError가 난다.
    stages = api.list_pumping_stages(PUMPING_CHAPTERS[chapter])
    at.sidebar.selectbox[0].set_value(next(s for s in stages if s["id"] == stage_id)).run()
    at.sidebar.radio[1].set_value(role).run()
    assert not at.exception, at.exception
    return at


def messages(at: AppTest) -> list[str]:
    return [m.value for m in list(at.success) + list(at.error) + list(at.info) + list(at.warning)]


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def finished(at: AppTest) -> bool:
    return any(b.label == "다시 하기" for b in at.button)


def play_break(at: AppTest, template: str, smash_i: int) -> list[str]:
    for _ in range(MAX_POINTS):
        at.text_input[0].set_value(template)
        button(at, "리시브").click().run()
        assert not at.exception, at.exception
        next(r for r in at.radio if r.label.startswith("4구")).set_value(smash_i)
        button(at, "스매시").click().run()
        assert not at.exception, at.exception
        if finished(at):
            return messages(at)
        button(at, "다음 포인트").click().run()
    raise AssertionError("경기가 끝나지 않았어요")


def play_defend(at: AppTest, stage_id: str, m: int, guard) -> list[str]:
    """guard(at, word)가 수비 슬라이더를 맞춘다."""
    for _ in range(MAX_POINTS):
        at.number_input[0].set_value(m)
        button(at, "서브").click().run()
        assert not at.exception, at.exception
        guard(at, at.session_state[f"{stage_id}-defend-game"]["word"])
        button(at, "수비").click().run()
        assert not at.exception, at.exception
        if finished(at):
            return messages(at)
        button(at, "다음 포인트").click().run()
    raise AssertionError("경기가 끝나지 않았어요")


# ---------- 시작과 설계 장 ----------


def test_app_starts_with_four_chapters():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert len(at.sidebar.radio[0].options) == 4


@pytest.mark.parametrize("chapter", ["1. DFA", "2. NFA"])
def test_design_chapter_grades_default_machine(chapter):
    """기본 입력(상태 q0, q1, 전이 없음)을 채점하면 오류 없이 결과(정답 또는 반례)가 나온다."""
    at = open_chapter(chapter)
    button(at, "채점하기").click().run()
    assert not at.exception, at.exception
    assert any("반례" in t or "정답" in t for t in messages(at))


# ---------- 정규 펌핑 게임 ----------


def test_regular_break_wins_with_anbn():
    # aⁿbⁿ에 a^m b^m, i = 0: Lemma가 어떤 분할로 막아도 뚫리므로 언제나 3 : 0
    at = open_game("3. 정규 펌핑 게임", "pump-01", BREAK)
    texts = play_break(at, "a^m b^m", 0)
    assert any("스테이지 클리어" in t for t in texts)
    assert any("정규 언어가 아니에요" in t for t in texts)
    assert any("증명문" in m.value for m in at.markdown)


def test_regular_defend_wins_on_even_a():
    # (aa)*에서 y = aa: 펌핑해도 a의 개수가 짝수로 남아서 언제나 막는다
    at = open_game("3. 정규 펌핑 게임", "pump-03", DEFEND)
    texts = play_defend(at, "pump-03", 3, lambda at, word: at.slider[0].set_value((0, 2)).run())
    assert any("Lemma를 지켰어요" in t for t in texts)
    assert any("정규 언어예요" in t for t in texts)


# ---------- 문맥자유 펌핑 게임 ----------


def test_cfl_break_wins_with_anbncn_and_shows_case_report():
    # aⁿbⁿcⁿ에 a^m b^m c^m, i = 0: 모든 경우가 i = 0으로 뚫린다
    at = open_game("4. 문맥자유 펌핑 게임", "cfl-01", BREAK)
    texts = play_break(at, "a^m b^m c^m", 0)
    assert any("스테이지 클리어" in t for t in texts)
    assert any("문맥자유 언어가 아니에요" in t for t in texts)
    assert any("경우별 정리" in m.value for m in at.markdown)


def straddle_ab(at: AppTest, word: str) -> None:
    """v = 마지막 a, y = 첫 b (슬라이더 ①로 vxy, ②로 그 안의 x를 빈 문자열로)."""
    k = word.index("b")
    at.slider[0].set_value((k - 1, k + 1)).run()
    at.slider[1].set_value((k, k)).run()


def test_cfl_defend_wins_on_anbn():
    # aⁿbⁿ은 문맥자유 언어: v = a, y = b로 두면 컴퓨터가 어떤 w를 보내도 막는다
    at = open_game("4. 문맥자유 펌핑 게임", "cfl-04", DEFEND)
    texts = play_defend(at, "cfl-04", 4, straddle_ab)
    assert any("Lemma를 지켰어요" in t for t in texts)
    assert any("문맥자유 언어예요" in t for t in texts)


# ---------- 경기 끝 안내 문구 ----------


@pytest.mark.parametrize(
    "chapter, stage_id, template, made, missing",
    [
        # 증명문을 만들 수 있는 리시브 / 없는 리시브 (지수가 m의 일차식이 아님)
        ("3. 정규 펌핑 게임", "pump-01", "a^m b^m", "증명문이에요", "자동으로 쓸 수 없어요"),
        ("3. 정규 펌핑 게임", "pump-01", "a^(m*m) b^(m*m)", "자동으로 쓸 수 없어요", "증명문이에요"),
        # 정리 표를 만들 수 있는 리시브 / 없는 리시브 (m에 따라 늘지 않는 블록)
        ("4. 문맥자유 펌핑 게임", "cfl-01", "a^m b^m c^m", "정리 표예요", "만들 수 없어요"),
        ("4. 문맥자유 펌핑 게임", "cfl-01", "a^7 b^7 c^7", "만들 수 없어요", "정리 표예요"),
    ],
)
def test_break_win_message_matches_whether_proof_was_made(chapter, stage_id, template, made, missing):
    """이긴 뒤 안내 줄('아래는 … 증명문/정리 표예요')과 아래 상자의 내용이 서로 어긋나지 않는다."""
    at = open_game(chapter, stage_id, BREAK)
    texts = play_break(at, template, 0)
    assert any("스테이지 클리어" in t for t in texts)
    assert any("가 아니에요" in t for t in texts)
    assert any(made in t for t in texts)
    assert not any(missing in t for t in texts)
