"""
Benchmark: MiniLang programs whose real behaviour we know by hand.
`truth` is what the program actually does with the given input on unbounded
integers. It is the ground truth the analyzer's answers are compared with.
"""
from .machine import Program

BENCHMARK = [
    Program("countdown", """
n = 10
while n > 0:
    n -= 1
""", truth="halts", note="textbook loop with a clear ranking function"),

    Program("sum_to_n", """
i = 0
s = 0
while i < n:
    s += i
    i += 1
""", inputs={"n": 50}, truth="halts"),

    Program("nested", """
i = 0
while i < n:
    j = 0
    while j < i:
        j += 1
    i += 1
""", inputs={"n": 30}, truth="halts", note="inner loop must be proved first"),

    Program("busy_wait", """
i = 0
while i < 1000000:
    i += 1
""", truth="halts", note="long but finite: fools a plain timeout"),

    Program("server_loop", """
requests = 0
while True:
    requests += 1
""", truth="loops", note="intentional infinite loop (event loop)"),

    Program("retry_with_break", """
tries = 0
while True:
    tries += 1
    if tries >= 5:
        break
""", truth="halts"),

    Program("wrong_direction", """
i = 10
while i > 0:
    i += 1
""", truth="loops", note="classic bug: ++ instead of --"),

    Program("forgot_update", """
x = 5
total = 0
while x > 0:
    total += x
""", truth="loops", note="loop variable never changed"),

    Program("swap_forever", """
x = 1
y = 2
while x != y:
    t = x
    x = y
    y = t
""", truth="loops", note="state cycles with period 2"),

    Program("skip_zero", """
x = 7
while x != 0:
    x -= 2
""", truth="loops", note="odd start, steps of 2: never hits 0"),

    Program("doubling", """
x = 1
while x > 0:
    x = x * 2
""", truth="loops", note="infinite on true integers; halts on 8-bit hardware (overflow)"),

    Program("gcd", """
while a != b:
    if a > b:
        a -= b
    else:
        b -= a
""", inputs={"a": 1071, "b": 462}, truth="halts", note="Euclid by subtraction"),

    Program("gcd_zero_bug", """
while a != b:
    if a > b:
        a -= b
    else:
        b -= a
""", inputs={"a": 0, "b": 5}, truth="loops", note="same code, input 0 -> b -= 0 forever"),

    Program("collatz_27", """
steps = 0
while n != 1:
    if n % 2 == 0:
        n = n // 2
    else:
        n = 3 * n + 1
    steps += 1
""", inputs={"n": 27}, truth="halts", note="nobody can prove Collatz halts for all n"),

    Program("collatz_0", """
steps = 0
while n != 1:
    if n % 2 == 0:
        n = n // 2
    else:
        n = 3 * n + 1
    steps += 1
""", inputs={"n": 0}, truth="loops", note="0 // 2 = 0, the counter keeps the state from repeating"),
]

BY_NAME = {p.name: p for p in BENCHMARK}
