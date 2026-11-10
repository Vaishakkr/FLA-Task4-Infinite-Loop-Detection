"""Rebuild docs/diagrams. Needs Graphviz."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from loopguard.tm import INCREMENT, PING_PONG  # noqa: E402

OUT = ROOT / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)


def save(name, dot):
    (OUT / f"{name}.dot").write_text(dot)
    subprocess.run(["dot", "-Gdpi=170", "-Tpng", "-o", str(OUT / f"{name}.png")], input=dot.encode(), check=True)
    subprocess.run(["dot", "-Tsvg", "-o", str(OUT / f"{name}.svg")], input=dot.encode(), check=True)
    print("wrote", name)


MAPPING = r'''
digraph M {
  rankdir=TB; nodesep=0.25; ranksep=0.45; newrank=true;
  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11 fillcolor="#eef3fb" color="#4a6fa5" width=2.4];
  edge [fontname="Helvetica" fontsize=10 color="#555555"];
  subgraph cluster_r { label="Real-world problem"; fontname="Helvetica-Bold"; color="#bbbbbb";
    r1 [label="Source program P\n(C / Python / Java)"];
    r2 [label="Input data w\n(file, request, sensor)"];
    r3 [label="Question:\n'will P hang on w?'"];
  }
  subgraph cluster_f { label="Computational formulation"; fontname="Helvetica-Bold"; color="#bbbbbb";
    f1 [label="Turing machine M_P\n(any program compiles to one)"];
    f2 [label="Tape contents w"];
    f3 [label="HALT = { <M, w> : M halts on w }\nLOOP = complement of HALT"];
  }
  subgraph cluster_a { label="What theory says"; fontname="Helvetica-Bold"; color="#bbbbbb";
    a1 [label="HALT is recognisable\n(run M, wait for halt)" fillcolor="#e6f4ea" color="#3a7d44"];
    a2 [label="HALT is undecidable\n(diagonal argument)" fillcolor="#fbe9e7" color="#b3412f"];
    a3 [label="LOOP is not even\nrecognisable" fillcolor="#fbe9e7" color="#b3412f"];
  }
  subgraph cluster_e { label="Engineering answer"; fontname="Helvetica-Bold"; color="#bbbbbb";
    e1 [label="Restrict the program class\n(ranking functions, recurrent sets)"];
    e2 [label="Restrict the machine\n(finite k-bit state: cycle detection)"];
    e3 [label="Approximate\n(timeouts, watchdogs: may be wrong)"];
  }
  e4 [label="Three-valued verdict:  HALTS / LOOPS / UNKNOWN" fillcolor="#fff4d6" color="#b08900" width=5];
  { rank=same; r1; r2; r3; }
  { rank=same; f1; f2; f3; }
  { rank=same; a1; a2; a3; }
  { rank=same; e1; e2; e3; }
  r1 -> f1; r2 -> f2; r3 -> f3;
  f3 -> a1; f3 -> a2; f3 -> a3;
  a2 -> e1; a2 -> e2; a2 -> e3;
  e1 -> e4; e2 -> e4; e3 -> e4;
}'''

PIPELINE = r'''
digraph P {
  rankdir=TB; node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11 fillcolor="#f4f6f9"];
  edge [fontname="Helvetica" fontsize=10];
  src [label="MiniLang program + input" shape=note fillcolor="#ffffff"];
  parse [label="Parse (Python ast, restricted subset)\ncompile to register-machine code"];
  st [label="Stage 1  Static analysis\nconstant guards, linear ranking function,\nrecurrent condition, != with constant step"];
  dyn [label="Stage 2  Run with configuration memory\nhalt seen -> HALTS\nrepeated (pc, vars) -> LOOPS"];
  fin [label="Stage 3  k-bit finite-state model\n(exact for k-bit hardware)"];
  h [label="HALTS + proof" fillcolor="#e6f4ea"];
  l [label="LOOPS + proof" fillcolor="#fbe9e7"];
  u [label="UNKNOWN\n(honest: no proof found)" fillcolor="#fff4d6"];
  src -> parse -> st;
  st -> h [label="ranking fn"]; st -> l [label="recurrent"]; st -> dyn [label="unknown"];
  dyn -> h [label="halted"]; dyn -> l [label="cycle"]; dyn -> u [label="budget"];
  dyn -> fin [style=dashed label="reported alongside"];
}'''

CLASSES = r'''
digraph C {
  node [fontname="Helvetica" fontsize=11]; compound=true;
  subgraph cluster_all { label="All languages"; fontname="Helvetica-Bold"; style=rounded; color="#999999";
    subgraph cluster_re { label="Turing-recognisable (RE)"; style="rounded,filled"; fillcolor="#eef3fb"; color="#4a6fa5";
      subgraph cluster_dec { label="Decidable"; style="rounded,filled"; fillcolor="#e6f4ea"; color="#3a7d44";
        d1 [label="A_DFA, EQ_DFA\nloops of a finite-state\nprogram (k-bit)" shape=plaintext];
        d2 [label="A_CFG, E_CFG" shape=plaintext];
      }
      re1 [label="HALT_TM\n'P halts on w'" shape=plaintext];
    }
    subgraph cluster_co { label="co-recognisable only"; style="rounded,filled"; fillcolor="#fbe9e7"; color="#b3412f";
      co1 [label="LOOP = complement of HALT_TM\n'P runs forever on w'" shape=plaintext];
    }
    n1 [label="neither: TOTAL_TM ('P halts on every input'),\nEQ_TM (program equivalence)" shape=plaintext];
  }
}'''

save("problem_mapping", MAPPING)
save("loopguard_pipeline", PIPELINE)
save("decidability_classes", CLASSES)
save("tm_increment", INCREMENT.to_dot())
save("tm_ping_pong", PING_PONG.to_dot())
