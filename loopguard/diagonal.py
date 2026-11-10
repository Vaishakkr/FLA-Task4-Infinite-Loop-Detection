"""
The diagonal argument, made executable.

Theorem (Turing 1936): no program H can decide, for every program P,
whether P halts.

Proof idea: given any candidate H, build
        D():  if H(D) says "halts":  loop forever
              else:                  halt
Then H's answer about D is always wrong.

We cannot run "loop forever" to completion, so programs here are Python
generators, and each `yield` is one step. A program that has not finished
after BUDGET steps is reported as "still running". By the construction of D,
"still running" really is "runs forever".

Every decider below is a real, terminating Python function. Each one is
wrong on its own D. That is the theorem in action, not a proof of it. The
proof is that the same construction works for *every* H.
"""
import inspect

BUDGET = 10_000


def observe(program):
    gen = program()
    for steps in range(BUDGET):
        try:
            next(gen)
        except StopIteration:
            return "halts", steps
    return "runs forever", BUDGET


def make_D(H):
    def D():
        if H(D) == "halts":
            while True:           # do the opposite: loop
                yield
        else:
            return                # do the opposite: halt
            yield                 # (makes D a generator)
    return D


# ------------------------------------------------------------ candidate H's
def H_optimist(P):
    "says every program halts"
    return "halts"


def H_pessimist(P):
    "says every program loops"
    return "loops"


def H_syntax(P):
    "looks for 'while True' in the source code"
    try:
        src = inspect.getsource(P)
    except (OSError, TypeError):
        return "halts"
    return "loops" if "while True" in src else "halts"


def make_H_timeout(limit=1000):
    depth = {"d": 0}

    def H_timeout(P):
        "runs P for a fixed number of steps; 'loops' if it is still running"
        if depth["d"] > 0:          # P is asking about itself while we simulate it
            return "loops"
        depth["d"] += 1
        try:
            gen = P()
            for _ in range(limit):
                try:
                    next(gen)
                except StopIteration:
                    return "halts"
            return "loops"
        finally:
            depth["d"] -= 1
    H_timeout.__doc__ = f"runs P for {limit} steps; says 'loops' if it has not stopped"
    return H_timeout


CANDIDATES = [H_optimist, H_pessimist, H_syntax, make_H_timeout(1000)]


def demonstrate():
    rows = []
    for H in CANDIDATES:
        D = make_D(H)
        predicted = H(D)
        actual, _ = observe(D)
        wrong = (predicted == "halts") != (actual == "halts")
        rows.append((H.__name__, (H.__doc__ or "").strip(), predicted, actual, wrong))
    return rows


def timeout_counterexample(limit=1000):
    """A fixed time limit is also wrong on ordinary halting programs."""
    def slow():
        for _ in range(limit + 1):
            yield
    H = make_H_timeout(limit)
    return H(slow), observe(slow)[0]
