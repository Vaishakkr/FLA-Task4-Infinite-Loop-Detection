"""
LoopGuard - terminal demo.

  python -m loopguard.cli theory       diagonal argument + Turing machine runs
  python -m loopguard.cli benchmark    analyzer on the 15 benchmark programs
  python -m loopguard.cli explain NAME full report for one benchmark program
  python -m loopguard.cli file.py      analyse your own MiniLang file
  python -m loopguard.cli all
"""
import sys
from pathlib import Path

from . import diagonal
from .analyzer import HALTS, LOOPS, check
from .machine import Program, listing
from .programs import BENCHMARK, BY_NAME
from .tm import MACHINES

C = sys.stdout.isatty() or "--color" in sys.argv
G, R, Y, B, D, E = ("\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[2m", "\033[0m") if C else ("",) * 6


def colour(v):
    return {HALTS: G, LOOPS: R}.get(v, Y) + v + E


def head(t):
    print(f"\n{B}{'=' * 78}\n{t}\n{'=' * 78}{E}")


def theory():
    head("1. Why no exact loop detector can exist - the diagonal program D")
    print("   For each candidate decider H we build D = 'if H(D) says halts: loop, else halt'.\n")
    print(f"   {'candidate H':<14}{'what it does':<54}{'H says':<9}{'D really':<14}")
    for name, doc, said, actual, wrong in diagonal.demonstrate():
        mark = f"{R}H WRONG{E}" if wrong else f"{G}ok{E}"
        print(f"   {name:<14}{doc[:52]:<54}{said:<9}{actual:<14}{mark}")
    said, actual = diagonal.timeout_counterexample(1000)
    print(f"\n   A 1000-step timeout on a program that stops after 1001 steps: says '{said}', really '{actual}'.")
    head("2. The same three outcomes on Turing machines")
    for tm, inp in MACHINES:
        r = tm.run(inp)
        res = {"halted": f"{G}HALTS{E}", "loops": f"{R}LOOPS (proved){E}", "budget": f"{Y}UNKNOWN{E}"}[r["result"]]
        print(f"\n   {B}{tm.name}{E} on '{inp or 'blank tape'}': {tm.description}")
        print("   IDs: " + " ⊢ ".join(r["trace"][:6]) + (" ⊢ ..." if len(r["trace"]) > 6 else ""))
        print(f"   -> {res} after {r['steps']} steps. {r.get('detail') or ''}")


def benchmark():
    head("3. LoopGuard on the benchmark (ground truth known by hand)")
    print(f"   {'program':<18}{'truth':<7}{'static':<10}{'run+cycle':<11}{'8-bit model':<13}"
          f"{'timeout only':<14}{'LoopGuard':<10}")
    stats = {"correct": 0, "unknown": 0, "wrong": 0, "watchdog_wrong": 0}
    for p in BENCHMARK:
        r = check(p)
        dyn = {"halted": "halts", "loops": "loops", "budget": "?"}[r["dynamic"]["result"]]
        fin = {"halted": "halts", "loops": "loops", "budget": "?"}[r["finite"]["result"]]
        v = r["verdict"]
        if v == "UNKNOWN":
            stats["unknown"] += 1
        elif v.lower() == p.truth:
            stats["correct"] += 1
        else:
            stats["wrong"] += 1
        wd = "halts" if r["watchdog"] == "HALTS" else "loops?"
        if (wd == "halts") != (p.truth == "halts"):
            stats["watchdog_wrong"] += 1
        wd_col = wd if (wd == "halts") == (p.truth == "halts") else f"{R}{wd}{E}"
        fin_col = fin if fin[:5] == p.truth[:5] else f"{Y}{fin}{E}"
        pad = len(R + E) if wd_col != wd else 0
        pad2 = len(Y + E) if fin_col != fin else 0
        print(f"   {p.name:<18}{p.truth:<7}{r['static']:<10}{dyn:<11}{fin_col:<{13 + pad2}}"
              f"{wd_col:<{14 + pad}}{colour(v)}")
    n = len(BENCHMARK)
    print(f"\n   LoopGuard: {stats['correct']}/{n} decided correctly, {stats['unknown']} UNKNOWN, "
          f"{stats['wrong']} wrong answers.")
    print(f"   Timeout-only watchdog (50 000 steps): {stats['watchdog_wrong']} wrong answer(s), and every 'loops?' it prints is a guess, not a proof.")
    print(f"   {D}8-bit column = exact answer for an 8-bit machine; yellow = differs from the "
          f"true-integer program because of overflow.{E}")


def explain(p):
    head(f"Program '{p.name}'  inputs={p.inputs or '{}'}  truth={p.truth}")
    print("   " + p.source.replace("\n", "\n   "))
    print(f"\n   {B}compiled register-machine code{E}")
    for line in listing(p):
        print("   " + line)
    r = check(p)
    print(f"\n   {B}static analysis{E}: {colour(r['static'])}")
    for why in r["static_reasons"]:
        print(f"     - {why}")
    d = r["dynamic"]
    print(f"   {B}execution with cycle detection{E}: {d['result']} after {d['steps']} steps {d['detail']}")
    f = r["finite"]
    print(f"   {B}8-bit finite-state model{E}: {f['result']} after {f['steps']} steps {f['detail']}")
    print(f"   {B}verdict{E}: {colour(r['verdict'])}  ({r['how']})")


def main(argv):
    args = [a for a in argv if a != "--color"] or ["all"]
    if args[0] == "theory":
        theory()
    elif args[0] == "benchmark":
        benchmark()
    elif args[0] == "explain" and len(args) > 1:
        explain(BY_NAME[args[1]])
    elif args[0] == "all":
        theory()
        benchmark()
    elif args[0].endswith(".py") and Path(args[0]).exists():
        explain(Program(Path(args[0]).stem, Path(args[0]).read_text()))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
