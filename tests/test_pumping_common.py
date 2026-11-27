"""공통 펌핑 엔진(pumping_common.py) 검사: 두 게임이 같이 쓰는 부품과 모듈 사이의 의존 방향."""

import ast
import random
from pathlib import Path

from catching_lemma.engine.cfl_pumping import CFLSplit, cfl_receive_scores
from catching_lemma.engine.pumping import Split, receive_scores
from catching_lemma.engine.pumping_common import (
    BlockLanguage,
    ReceiveScore,
    choose_defense,
    pick_receive,
    winning_receives,
)

ENGINE = Path(__file__).resolve().parent.parent / "catching_lemma" / "engine"
ANBN = BlockLanguage(["a", "b"], "n0 == n1")


def imported_names(source: str) -> set[str]:
    """소스가 import하는 모듈 이름(마지막 부분)과 from-import로 가져오는 이름.

    상대·절대 경로를 같은 이름으로 본다: from .pumping, from catching_lemma.engine.pumping → "pumping".
    from . import pumping, from catching_lemma.engine import pumping처럼 모듈을 이름으로 가져오는 경우도 잡도록
    from-import의 이름도 넣는다. 함수 안의 import도 찾는다(ast.walk).
    """
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.rsplit(".", 1)[-1])
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            found.update(a.name.rsplit(".", 1)[-1] for a in node.names)
    return found


def imported_modules(name: str) -> set[str]:
    return imported_names((ENGINE / name).read_text(encoding="utf-8"))


def test_imported_names_catches_every_import_form():
    """의존 방향 검사가 import 형태에 따라 빠지지 않는지 (이 검사 자체의 테스트)."""
    forms = [
        "from .pumping import pump",
        "from catching_lemma.engine.pumping import pump",
        "from . import pumping",
        "from catching_lemma.engine import pumping",
        "import catching_lemma.engine.pumping",
        "def f():\n    from .pumping import pump",
    ]
    for source in forms:
        assert "pumping" in imported_names(source), source
    assert "pumping" not in imported_names("from .pumping_common import evaluate")


def test_dependency_direction():
    """공통 엔진은 두 게임을 모르고, 두 게임은 서로를 모른다 (둘 다 공통 엔진만 쓴다)."""
    assert not {"pumping", "cfl_pumping"} & imported_modules("pumping_common.py")
    assert "cfl_pumping" not in imported_modules("pumping.py")
    assert "pumping" not in imported_modules("cfl_pumping.py")
    assert "pumping_common" in imported_modules("pumping.py")
    assert "pumping_common" in imported_modules("cfl_pumping.py")


def test_choose_defense_works_for_both_split_shapes():
    rng = random.Random(0)
    regular = [Split(0, 1, [0, 2]), Split(1, 2, [])]
    assert choose_defense(regular, rng, random_rate=0.0) == (regular[1], "tough")
    cfl = [CFLSplit((0, 1, 1, 2), (0,)), CFLSplit((1, 2, 2, 3), (0, 2))]
    assert choose_defense(cfl, rng, random_rate=0.0) == (cfl[0], "tough")


def test_pick_receive_and_winning_receives_use_only_scores():
    scores = (ReceiveScore("aabb", 3, 3), ReceiveScore("aaabbb", 3, 3), ReceiveScore("ab", 1, 2))
    best = pick_receive(scores, random.Random(0), rate=0.0)
    assert best.word == "aabb" and best.mode == "best" and best.winning  # 동률이면 짧은 것
    mistake = pick_receive(scores, random.Random(0), rate=1.0)
    assert mistake.word == "ab" and mistake.mode == "mistake" and not mistake.winning
    assert winning_receives(scores) == (["aabb", "aaabbb"], 3)
    assert pick_receive((), random.Random(0), rate=0.0) is None


def test_both_games_feed_the_same_receive_picker():
    for scores in (receive_scores(ANBN, 3), cfl_receive_scores(ANBN, 3)):
        assert all(isinstance(s, ReceiveScore) for s in scores)
        assert pick_receive(scores, random.Random(1), rate=0.0) is not None
