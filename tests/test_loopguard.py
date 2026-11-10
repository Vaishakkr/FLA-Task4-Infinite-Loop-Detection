"""Validation suite (owner: Deepak V F).

Main property: LoopGuard is SOUND. Whenever it says HALTS or LOOPS, that
answer is right. UNKNOWN is allowed, wrong answers are not.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loopguard import diagonal  # noqa: E402
from loopguard.analyzer import HALTS, LOOPS, UNKNOWN, check, static_analysis  # noqa: E402
from loopguard.machine import MiniLangError, Program, run  # noqa: E402
from loopguard.programs import BENCHMARK  # noqa: E402
from loopguard.tm import INCREMENT, PING_PONG, RUNAWAY  # noqa: E402


@pytest.mark.parametrize("p", BENCHMARK, ids=lambda p: p.name)
def test_benchmark_never_wrong(p):
    v = check(p)["verdict"]
    assert v == UNKNOWN or v.lower() == p.truth


def test_benchmark_decides_most():
    decided = sum(check(p)["verdict"] != UNKNOWN for p in BENCHMARK)
    assert decided >= 13


def test_soundness_on_many_inputs():
    """Run the static analyzer on families of programs over a grid of inputs and
    compare with long concrete runs (only where a long run actually settles it)."""
    templates = [
        "while x > 0:\n    x -= {d}",
        "while x < y:\n    x += {d}",
        "while x != y:\n    x += {d}",
        "while x > y:\n    x += {d}\n    y += 1",
        "while x >= 0:\n    x -= {d}\n    if x == 3:\n        x -= 1",
    ]
    for t in templates:
        for d in (-2, -1, 0, 1, 2, 3):
            for x in range(-4, 6):
                for y in range(-3, 5):
                    src = f"x = {x}\ny = {y}\n" + t.format(d=d)
                    p = Program("t", src)
                    v, _ = static_analysis(p)
                    r = run(p, max_steps=5000)
                    if v == HALTS:
                        assert r["result"] == "halted", src
                    elif v == LOOPS:
                        assert r["result"] != "halted", src


def test_cycle_detection_is_proof():
    p = Program("cyc", "x = 1\ny = 2\nwhile x != y:\n    t = x\n    x = y\n    y = t")
    r = run(p)
    assert r["result"] == "loops"


def test_finite_model_always_decides():
    for p in BENCHMARK:
        r = run(p, bits=4, max_steps=10 ** 6)
        assert r["result"] in ("halted", "loops"), p.name


def test_minilang_rejects_unsupported_code():
    with pytest.raises(MiniLangError):
        Program("bad", "import os")
    with pytest.raises(MiniLangError):
        Program("bad", "def f():\n    pass")


def test_every_candidate_decider_is_wrong_on_its_diagonal_program():
    for _name, _doc, _said, _actual, wrong in diagonal.demonstrate():
        assert wrong


def test_timeout_is_not_a_decider():
    said, actual = diagonal.timeout_counterexample(500)
    assert said == "loops" and actual == "halts"


def test_turing_machines():
    r = INCREMENT.run("1011")
    assert r["result"] == "halted" and r["final"].replace("[done]", "") == "1100"
    assert PING_PONG.run("0")["result"] == "loops"
    assert RUNAWAY.run("", max_steps=2000)["result"] == "budget"
