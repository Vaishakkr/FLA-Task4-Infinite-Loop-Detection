"""
A single-tape Turing machine simulator, used to show the same three
outcomes on the formal model itself:

  * the machine halts                -> we see it  (HALT_TM is Turing-recognisable)
  * an instantaneous description repeats -> proven loop
  * neither, within the budget        -> UNKNOWN (the general case)
"""

BLANK = "_"


class TM:
    def __init__(self, name, delta, start, halt_states, description=""):
        """delta: {(state, symbol): (new_state, write, move)} with move in 'LRS'."""
        self.name = name
        self.delta = delta
        self.start = start
        self.halt = set(halt_states)
        self.description = description

    def run(self, tape_input, max_steps=10_000, keep=12):
        tape = dict(enumerate(tape_input))
        head, state = 0, self.start
        seen = {}
        trace = []
        for step in range(max_steps + 1):
            idd = self.id_string(tape, head, state)
            if len(trace) < keep:
                trace.append(idd)
            if state in self.halt:
                return {"result": "halted", "steps": step, "trace": trace, "final": idd}
            key = (state, head, tuple(sorted((k, v) for k, v in tape.items() if v != BLANK)))
            if key in seen:
                return {"result": "loops", "steps": step, "trace": trace, "final": idd,
                        "detail": f"ID at step {step} repeats the ID at step {seen[key]}"}
            seen[key] = step
            sym = tape.get(head, BLANK)
            if (state, sym) not in self.delta:
                return {"result": "halted", "steps": step, "trace": trace, "final": idd,
                        "detail": "no transition (implicit reject)"}
            state, write, move = self.delta[(state, sym)]
            tape[head] = write
            head += {"L": -1, "R": 1, "S": 0}[move]
        return {"result": "budget", "steps": max_steps, "trace": trace,
                "final": self.id_string(tape, head, state),
                "detail": "IDs keep growing, none repeats"}

    @staticmethod
    def id_string(tape, head, state):
        cells = [k for k, v in tape.items() if v != BLANK] + [head]
        lo, hi = min(cells), max(cells)
        s = "".join(tape.get(i, BLANK) for i in range(lo, head)) + f"[{state}]" + \
            "".join(tape.get(i, BLANK) for i in range(head, hi + 1))
        return s

    def to_dot(self):
        out = [f'digraph "{self.name}" {{', "rankdir=LR;",
               'node [shape=circle fontname="Helvetica" fontsize=12];',
               'edge [fontname="Helvetica" fontsize=10];', "__s [shape=point];"]
        for h in self.halt:
            out.append(f'"{h}" [shape=doublecircle];')
        out.append(f'__s -> "{self.start}";')
        edges = {}
        for (q, a), (p, b, m) in self.delta.items():
            edges.setdefault((q, p), []).append(f"{a}/{b},{m}")
        for (q, p), labs in edges.items():
            out.append(f'"{q}" -> "{p}" [label="{"\\n".join(labs)}"];')
        out.append("}")
        return "\n".join(out)


# Binary increment: walks to the right end, then adds 1 with carry. Halts.
INCREMENT = TM("binary increment", {
    ("right", "0"): ("right", "0", "R"), ("right", "1"): ("right", "1", "R"),
    ("right", BLANK): ("carry", BLANK, "L"),
    ("carry", "1"): ("carry", "0", "L"), ("carry", "0"): ("done", "1", "S"),
    ("carry", BLANK): ("done", "1", "S"),
}, "right", {"done"}, "adds 1 to a binary number; always halts")

# Ping-pong between two cells forever: a bounded-space loop.
PING_PONG = TM("ping-pong", {
    ("a", "0"): ("b", "0", "R"), ("a", BLANK): ("b", BLANK, "R"),
    ("b", "0"): ("a", "0", "L"), ("b", BLANK): ("a", BLANK, "L"),
}, "a", {"halt"}, "moves right, left, right, ... on two cells; the ID repeats")

# Writes 1s to the right forever: an unbounded-space loop.
RUNAWAY = TM("runaway writer", {
    ("w", BLANK): ("w", "1", "R"), ("w", "0"): ("w", "1", "R"), ("w", "1"): ("w", "1", "R"),
}, "w", {"halt"}, "never halts, but no ID ever repeats because the tape keeps growing")

MACHINES = [(INCREMENT, "1011"), (PING_PONG, "0"), (RUNAWAY, "")]
