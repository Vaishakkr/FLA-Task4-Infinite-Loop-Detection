"""
MiniLang: a tiny imperative language and the machine that runs it.

MiniLang uses Python syntax but only allows:
    x = expr      x += expr  (also -=, *=)
    while cond:   if cond: ... else: ...   break   pass
with integer/boolean expressions (+ - * // %, comparisons, and/or/not).

Programs are compiled to a flat list of instructions, which makes this a
register machine (a Minsky-style counter machine with richer arithmetic):

    ("set", var, expr)       assign
    ("jf", cond, target)     jump to target if cond is false
    ("jmp", target)          unconditional jump
    ("halt",)

A *configuration* of the machine is (program counter, values of all
variables). This is the analogue of a Turing machine's instantaneous
description, and it is what loop detection works with.
"""
import ast

ALLOWED_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
                  ast.Mult: lambda a, b: a * b, ast.FloorDiv: lambda a, b: a // b if b else 0,
                  ast.Mod: lambda a, b: a % b if b else 0}
ALLOWED_CMP = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
               ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
               ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


class MiniLangError(ValueError):
    pass


def parse(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        ok = isinstance(node, (ast.Module, ast.Assign, ast.AugAssign, ast.While, ast.If,
                               ast.Pass, ast.Break, ast.Name, ast.Constant, ast.BinOp,
                               ast.UnaryOp, ast.Compare, ast.BoolOp, ast.Load, ast.Store,
                               ast.And, ast.Or, ast.Not, ast.USub, ast.expr_context,
                               ast.operator, ast.cmpop, ast.boolop, ast.unaryop))
        if not ok:
            raise MiniLangError(f"not allowed in MiniLang: {type(node).__name__} (line {getattr(node, 'lineno', '?')})")
        if isinstance(node, ast.BinOp) and type(node.op) not in ALLOWED_BINOPS:
            raise MiniLangError(f"operator {type(node.op).__name__} not allowed")
        if isinstance(node, ast.Assign) and (len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name)):
            raise MiniLangError("only simple assignments x = expr")
    return tree


def evaluate(e, env, wrap=None):
    if isinstance(e, ast.Constant):
        v = int(e.value)
    elif isinstance(e, ast.Name):
        v = env.get(e.id, 0)
    elif isinstance(e, ast.BinOp):
        v = ALLOWED_BINOPS[type(e.op)](evaluate(e.left, env, wrap), evaluate(e.right, env, wrap))
    elif isinstance(e, ast.UnaryOp):
        x = evaluate(e.operand, env, wrap)
        v = -x if isinstance(e.op, ast.USub) else int(not x)
    elif isinstance(e, ast.BoolOp):
        vals = [evaluate(x, env, wrap) for x in e.values]
        v = int(all(vals)) if isinstance(e.op, ast.And) else int(any(vals))
    elif isinstance(e, ast.Compare):
        left = evaluate(e.left, env, wrap)
        v = 1
        for op, right_e in zip(e.ops, e.comparators):
            right = evaluate(right_e, env, wrap)
            if not ALLOWED_CMP[type(op)](left, right):
                v = 0
                break
            left = right
    else:
        raise MiniLangError(type(e).__name__)
    return wrap(v) if wrap else v


def compile_program(tree):
    code = []

    def emit(ins):
        code.append(ins)
        return len(code) - 1

    def block(stmts, breaks):
        for s in stmts:
            stmt(s, breaks)

    def stmt(s, breaks):
        if isinstance(s, ast.Assign):
            emit(("set", s.targets[0].id, s.value))
        elif isinstance(s, ast.AugAssign):
            emit(("set", s.target.id, ast.BinOp(ast.Name(s.target.id, ast.Load()), s.op, s.value)))
        elif isinstance(s, ast.Pass):
            pass
        elif isinstance(s, ast.Break):
            if breaks is None:
                raise MiniLangError("break outside loop")
            breaks.append(emit(["jmp", None]))
        elif isinstance(s, ast.If):
            j = emit(["jf", s.test, None])
            block(s.body, breaks)
            if s.orelse:
                k = emit(["jmp", None])
                code[j][2] = len(code)
                block(s.orelse, breaks)
                code[k][1] = len(code)
            else:
                code[j][2] = len(code)
        elif isinstance(s, ast.While):
            top = len(code)
            j = emit(["jf", s.test, None])
            my_breaks = []
            block(s.body, my_breaks)
            emit(("jmp", top))
            end = len(code)
            code[j][2] = end
            for b in my_breaks:
                code[b][1] = end
        else:
            raise MiniLangError(type(s).__name__)

    block(tree.body, None)
    emit(("halt",))
    return [tuple(c) for c in code]


class Program:
    def __init__(self, name, source, inputs=None, truth=None, note=""):
        self.name = name
        self.source = source.strip("\n")
        self.inputs = dict(inputs or {})
        self.truth = truth          # "halts" / "loops" / None (unknown to us)
        self.note = note
        self.tree = parse(self.source)
        self.code = compile_program(self.tree)

    def variables(self):
        names = set(self.inputs)
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Name):
                names.add(n.id)
        return sorted(names)


def run(program, inputs=None, max_steps=100_000, bits=None, detect_cycles=True):
    """Execute the program.

    bits=None : unbounded Python integers (a real infinite-state machine)
    bits=k    : every value wraps modulo 2^k, like a k-bit CPU register.
                The machine then has finitely many configurations.

    Returns dict(result, steps, env, detail) where result is
      "halted"       - reached the halt instruction
      "loops"        - a configuration repeated, so it will repeat forever
                       (the machine is deterministic); this is a proof
      "budget"       - ran out of steps without deciding anything
    """
    wrap = None
    if bits:
        m = 1 << bits

        def wrap(v):
            return v % m
    env = {v: 0 for v in program.variables()}
    env.update(program.inputs if inputs is None else inputs)
    if wrap:
        env = {k: wrap(v) for k, v in env.items()}
    names = sorted(env)
    seen = {}
    pc, steps = 0, 0
    code = program.code
    while steps < max_steps:
        ins = code[pc]
        if ins[0] == "halt":
            return {"result": "halted", "steps": steps, "env": env, "detail": ""}
        if detect_cycles:
            cfg = (pc,) + tuple(env[n] for n in names)
            if cfg in seen:
                first = seen[cfg]
                return {"result": "loops", "steps": steps, "env": env,
                        "detail": f"configuration at step {steps} equals the one at step {first} "
                                  f"(cycle length {steps - first})"}
            seen[cfg] = steps
        if ins[0] == "set":
            env[ins[1]] = evaluate(ins[2], env, wrap)
            pc += 1
        elif ins[0] == "jf":
            pc = pc + 1 if evaluate(ins[1], env, wrap) else ins[2]
        elif ins[0] == "jmp":
            pc = ins[1]
        steps += 1
    return {"result": "budget", "steps": steps, "env": env,
            "detail": f"no halt and no repeated configuration within {max_steps} steps"}


def listing(program):
    out = []
    for i, ins in enumerate(program.code):
        if ins[0] == "set":
            out.append(f"{i:>3}: {ins[1]} := {ast.unparse(ins[2])}")
        elif ins[0] == "jf":
            out.append(f"{i:>3}: if not ({ast.unparse(ins[1])}) goto {ins[2]}")
        elif ins[0] == "jmp":
            out.append(f"{i:>3}: goto {ins[1]}")
        else:
            out.append(f"{i:>3}: halt")
    return out
