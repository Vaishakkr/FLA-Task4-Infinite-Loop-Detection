"""
Restricted-case loop detection.

The general question "does program P halt on input w?" is undecidable
(HALT_TM), so this analyzer never claims to answer it for every program. It
always returns one of three verdicts:

    HALTS    - with a proof (ranking function, or it actually halted)
    LOOPS    - with a proof (recurrent condition, or a repeated configuration)
    UNKNOWN  - none of the sound techniques applied

The techniques, in the order they are tried:

  1. Static: constant guards (while True without break / while False)
  2. Static: linear ranking function r = b - a for guards a < b, a <= b, ...
     that drops by >= 1 on every path through the loop body  -> HALTS
  3. Static: recurrent condition - the guard is a > b and a - b never decreases
     on any path, and the guard is true when the loop is reached -> LOOPS
  4. Dynamic: run the program and remember every configuration (pc, vars).
     Halting is observed directly (HALT is recognisable). A repeated
     configuration of a deterministic machine proves an infinite loop.
  5. Finite-state model: wrap all values to k bits. The machine now has at
     most (#pc) * 2^(k * #vars) configurations, so step 4 always gives an
     exact answer - for the k-bit machine, not the mathematical program.
"""
import ast
from itertools import product

from .machine import evaluate, run

HALTS, LOOPS, UNKNOWN = "HALTS", "LOOPS", "UNKNOWN"


# ------------------------------------------------------------ linear algebra
def linear(e):
    """Return ({var: coef}, const) if e is linear in the variables, else None."""
    if isinstance(e, ast.Constant):
        return {}, int(e.value)
    if isinstance(e, ast.Name):
        return {e.id: 1}, 0
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub):
        r = linear(e.operand)
        return ({k: -v for k, v in r[0].items()}, -r[1]) if r else None
    if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Add, ast.Sub)):
        a, b = linear(e.left), linear(e.right)
        if not a or not b:
            return None
        s = 1 if isinstance(e.op, ast.Add) else -1
        out = dict(a[0])
        for k, v in b[0].items():
            out[k] = out.get(k, 0) + s * v
        return out, a[1] + s * b[1]
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult):
        a, b = linear(e.left), linear(e.right)
        if a and b and not a[0]:
            return {k: a[1] * v for k, v in b[0].items()}, a[1] * b[1]
        if a and b and not b[0]:
            return {k: b[1] * v for k, v in a[0].items()}, a[1] * b[1]
    return None


def lin_sub(a, b):
    out = dict(a[0])
    for k, v in b[0].items():
        out[k] = out.get(k, 0) - v
    return {k: v for k, v in out.items() if v}, a[1] - b[1]


def lin_text(r):
    coefs, c = r
    parts = []
    for k, v in sorted(coefs.items()):
        parts.append(("+ " if v > 0 else "- ") + (f"{abs(v)}*" if abs(v) != 1 else "") + k)
    if c:
        parts.append(("+ " if c > 0 else "- ") + str(abs(c)))
    s = " ".join(parts).lstrip("+ ").strip()
    return s if not s.startswith("- ") else "-" + s[2:]


# ------------------------------------------------------- effects of a body
class GiveUp(Exception):
    pass


def assigned_vars(stmts):
    out = set()
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, ast.Assign):
                out.add(n.targets[0].id)
            elif isinstance(n, ast.AugAssign):
                out.add(n.target.id)
    return out


def path_deltas(stmts, watch, limit=64):
    """All possible {var: delta} effects of one pass through stmts, for the
    watched variables. Raises GiveUp if a watched variable gets a non-constant
    update. Paths that execute `break` are dropped (they leave the loop)."""
    paths = [dict()]
    for s in stmts:
        new = []
        for p in paths:
            for q in _stmt_deltas(s, watch, limit):
                if q is None:            # break
                    continue
                merged = dict(p)
                for k, v in q.items():
                    merged[k] = merged.get(k, 0) + v
                new.append(merged)
        paths = new[:limit]
        if not paths:
            return []
    return paths


def _stmt_deltas(s, watch, limit):
    if isinstance(s, ast.Pass):
        return [{}]
    if isinstance(s, ast.Break):
        return [None]
    if isinstance(s, (ast.Assign, ast.AugAssign)):
        var = s.targets[0].id if isinstance(s, ast.Assign) else s.target.id
        if var not in watch:
            return [{}]
        if isinstance(s, ast.AugAssign):
            r = linear(s.value)
            if r and not r[0] and isinstance(s.op, (ast.Add, ast.Sub)):
                return [{var: r[1] if isinstance(s.op, ast.Add) else -r[1]}]
            raise GiveUp(f"{var} updated by '{ast.unparse(s)}'")
        r = linear(s.value)
        if r and r[0] == {var: 1}:
            return [{var: r[1]}]
        raise GiveUp(f"{var} updated by '{ast.unparse(s)}'")
    if isinstance(s, ast.If):
        a = path_deltas(s.body, watch, limit)
        b = path_deltas(s.orelse, watch, limit) if s.orelse else [{}]
        return (a + b)[:limit] or [None]
    if isinstance(s, ast.While):
        if assigned_vars(s.body) & watch:
            raise GiveUp("an inner loop changes the ranking variables")
        v, why = analyze_loop(s, {})
        if v != HALTS:
            raise GiveUp(f"inner loop not proved terminating ({why})")
        return [{}]
    raise GiveUp(type(s).__name__)


def has_direct_break(stmts):
    for s in stmts:
        if isinstance(s, ast.Break):
            return True
        if isinstance(s, ast.If) and (has_direct_break(s.body) or has_direct_break(s.orelse)):
            return True
    return False


# ----------------------------------------------------------- one loop
def analyze_loop(loop, known):
    """Return (verdict, reason) for a single while loop.
    known: variables whose values are known constants when the loop starts."""
    g = loop.test
    if isinstance(g, ast.Constant):
        if not g.value:
            return HALTS, "guard is constantly false"
        if not has_direct_break(loop.body):
            return LOOPS, "guard is constantly true and the body has no break"
        return UNKNOWN, "while True with a break: exits only if the break is reached"
    if not (isinstance(g, ast.Compare) and len(g.ops) == 1):
        return UNKNOWN, f"guard '{ast.unparse(g)}' is not a single comparison"
    a, b = linear(g.left), linear(g.comparators[0])
    if a is None or b is None:
        return UNKNOWN, f"guard '{ast.unparse(g)}' is not linear"
    op = type(g.ops[0])
    if op in (ast.Lt, ast.LtE):
        r = lin_sub(b, a)                      # loop runs while r > 0 (or >= 0)
    elif op in (ast.Gt, ast.GtE):
        r = lin_sub(a, b)
    elif op is ast.NotEq:
        return _not_equal_loop(loop, lin_sub(a, b), known)
    else:
        sym = {ast.Eq: "=="}.get(op, op.__name__)
        return UNKNOWN, f"guard uses '{sym}': no linear ranking function of the form b - a"
    watch = set(r[0])
    try:
        paths = path_deltas(loop.body, watch)
    except GiveUp as why:
        return UNKNOWN, str(why)
    if not paths:
        return HALTS, "every path through the body executes break"
    changes = [sum(r[0][v] * d.get(v, 0) for v in watch) for d in paths]
    rtxt = lin_text(r)
    if max(changes) <= -1:
        return HALTS, (f"ranking function r = {rtxt}: the guard needs r {'>' if op in (ast.Lt, ast.Gt) else '>='} 0 "
                       f"and every path lowers r by at least {-max(changes)}")
    if min(changes) >= 0 and not has_direct_break(loop.body):
        if known is not None and all(v in known for v in watch):
            env = dict(known)
            if evaluate(g, env):
                return LOOPS, (f"recurrent condition: r = {rtxt} never decreases (change per pass "
                               f"{min(changes)}..{max(changes)}) and the guard is true on entry")
            return HALTS, "guard is false on entry, the body never runs"
        return UNKNOWN, f"loops whenever entered (r = {rtxt} never decreases), but entry values unknown"
    return UNKNOWN, f"r = {rtxt} changes by {sorted(set(changes))} depending on the path"


def _not_equal_loop(loop, r, known):
    """while a != b where r = a - b moves by the same constant d on every path.
    With the entry value r0 known: the loop exits iff r reaches exactly 0,
    i.e. iff d != 0, r0 and d have opposite signs (or r0 = 0) and d divides r0."""
    rtxt = lin_text(r)
    watch = set(r[0])
    try:
        paths = path_deltas(loop.body, watch)
    except GiveUp as why:
        return UNKNOWN, f"guard '{rtxt} != 0': {why}"
    if has_direct_break(loop.body) or not paths:
        return UNKNOWN, "!= guard together with break"
    changes = {sum(r[0][v] * p.get(v, 0) for v in watch) for p in paths}
    if len(changes) != 1:
        return UNKNOWN, f"guard '{rtxt} != 0' and r changes by {sorted(changes)} depending on the path"
    d = changes.pop()
    if known is None or not all(v in known for v in watch):
        return UNKNOWN, f"r = {rtxt} moves by {d} per pass; answer depends on the unknown entry value"
    r0 = sum(c * known[v] for v, c in r[0].items()) + r[1]
    if r0 == 0:
        return HALTS, "guard is false on entry"
    if d != 0 and (r0 > 0) != (d > 0) and r0 % abs(d) == 0:
        return HALTS, f"r = {rtxt} starts at {r0} and moves by {d}: reaches 0 after {abs(r0 // d)} passes"
    return LOOPS, (f"r = {rtxt} starts at {r0} and moves by {d} per pass: it "
                   f"{'never changes' if d == 0 else 'moves away from 0' if (r0 > 0) == (d > 0) else 'jumps over 0'}, "
                   "so the guard stays true")


# --------------------------------------------------------- whole program
def static_analysis(program):
    """Walk the top-level statements, tracking constants from straight-line
    code, and combine the per-loop verdicts."""
    known = dict(program.inputs)
    reasons = []
    for s in program.tree.body:
        if isinstance(s, (ast.Assign, ast.AugAssign)):
            var = s.targets[0].id if isinstance(s, ast.Assign) else s.target.id
            expr = s.value if isinstance(s, ast.Assign) else ast.BinOp(ast.Name(var, ast.Load()), s.op, s.value)
            names = {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}
            if names <= set(known):
                known[var] = evaluate(expr, known)
            else:
                known.pop(var, None)
            continue
        if isinstance(s, ast.Pass):
            continue
        if isinstance(s, ast.While):
            v, why = analyze_loop(s, known)
            reasons.append(f"loop at line {s.lineno}: {v} - {why}")
            if v == LOOPS:
                return LOOPS, reasons
            if v == UNKNOWN:
                return UNKNOWN, reasons
            for var in assigned_vars([s]):
                known.pop(var, None)
            continue
        if isinstance(s, ast.If):
            loops = [n for n in ast.walk(s) if isinstance(n, ast.While)]
            for lp in loops:
                v, why = analyze_loop(lp, None)
                reasons.append(f"loop at line {lp.lineno} (inside if): {v} - {why}")
                if v != HALTS:
                    return UNKNOWN, reasons
            for var in assigned_vars([s]):
                known.pop(var, None)
            continue
        return UNKNOWN, reasons + [f"unsupported top-level {type(s).__name__}"]
    if not reasons:
        reasons.append("no loops: straight-line code always halts")
    return HALTS, reasons


def check(program, max_steps=50_000, bits=8):
    """Full pipeline. Returns a dict with every stage's answer."""
    sv, sreasons = static_analysis(program)
    dyn = run(program, max_steps=max_steps)
    fin = run(program, max_steps=10 ** 7, bits=bits) if bits else None
    watchdog = run(program, max_steps=max_steps, detect_cycles=False)
    if sv != UNKNOWN:
        verdict, how = sv, "static analysis"
    elif dyn["result"] == "halted":
        verdict, how = HALTS, f"execution halted after {dyn['steps']} steps"
    elif dyn["result"] == "loops":
        verdict, how = LOOPS, "repeated configuration: " + dyn["detail"]
    else:
        verdict, how = UNKNOWN, "no proof either way within the budget"
    return {
        "static": sv, "static_reasons": sreasons,
        "dynamic": dyn, "finite": fin,
        "watchdog": "HALTS" if watchdog["result"] == "halted" else "LOOPS?",
        "verdict": verdict, "how": how,
    }


def all_inputs(names, lo, hi):
    for vals in product(range(lo, hi + 1), repeat=len(names)):
        yield dict(zip(names, vals))
