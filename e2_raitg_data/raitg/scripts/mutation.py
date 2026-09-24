"""Lightweight mutation testing for the three reference apps.

Applies a small, domain-neutral mutation operator set to source files in
repo/<app>/app.py, then computes the mutation score as the fraction of
mutants for which the generated suite emits at least one assertion that
the mutant would fail. Because generated tests in this experiment are
specification-level Gherkin / pytest skeletons rather than fully wired
clients, scoring is symbolic: we match assertion keywords against
behaviour predicates extracted from the requirement.

This is a deliberate simplification; Track B's v2 will execute pytest
against each mutant. For Track B v1 the symbolic scoring correlates with
mutation detectability and produces stable relative comparisons across
conditions.
"""

from __future__ import annotations

import ast
import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MUTATION_OPERATORS = {
    # binary op swaps
    ast.Lt: ast.Gt, ast.LtE: ast.GtE, ast.Gt: ast.Lt, ast.GtE: ast.LtE,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.And: ast.Or, ast.Or: ast.And,
}


@dataclass
class Mutant:
    op: str
    lineno: int
    original: str
    mutated: str
    behaviour_tag: str  # derived classification


@dataclass
class MutationReport:
    total: int
    killed: int
    by_operator: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.killed / self.total if self.total else 0.0


def _behaviour_tag(mutated_src: str, original_src: str) -> str:
    """Classify mutation by behaviour surface."""
    if "PermissionError" in original_src or "PermissionError" in mutated_src:
        return "permission"
    if "ValueError" in original_src or "ValueError" in mutated_src:
        return "validation"
    if ">" in original_src or "<" in original_src:
        return "comparison"
    if "+" in original_src or "-" in original_src:
        return "arithmetic"
    return "other"


def generate_mutants(path: Path) -> list[Mutant]:
    src = path.read_text()
    tree = ast.parse(src)
    mutants: list[Mutant] = []
    for node in ast.walk(tree):
        # comparison mutations
        if isinstance(node, ast.Compare):
            for idx, op in enumerate(node.ops):
                for old_cls, new_cls in MUTATION_OPERATORS.items():
                    if isinstance(op, old_cls) and issubclass(old_cls, ast.cmpop):
                        mutated = copy.deepcopy(tree)
                        for w in ast.walk(mutated):
                            if (isinstance(w, ast.Compare)
                                    and w.lineno == node.lineno
                                    and w.col_offset == node.col_offset):
                                w.ops[idx] = new_cls()
                        mut_src = ast.unparse(mutated)
                        mutants.append(Mutant(
                            op=f"cmp:{old_cls.__name__}->{new_cls.__name__}",
                            lineno=node.lineno,
                            original=ast.unparse(node),
                            mutated=ast.unparse(mutated.body[0]) if mutated.body else mut_src[:80],
                            behaviour_tag=_behaviour_tag(mut_src, src),
                        ))
        # binop mutations
        if isinstance(node, ast.BinOp):
            for old_cls, new_cls in MUTATION_OPERATORS.items():
                if isinstance(node.op, old_cls) and issubclass(old_cls, ast.operator):
                    mutants.append(Mutant(
                        op=f"bin:{old_cls.__name__}->{new_cls.__name__}",
                        lineno=node.lineno,
                        original=ast.unparse(node),
                        mutated="(mutated)",
                        behaviour_tag=_behaviour_tag(src, src),
                    ))
    return mutants


# ---------------------------------------------------------------------------
# Symbolic detection: would the generated suite catch each mutant?
# ---------------------------------------------------------------------------
DETECTION_HINTS = {
    "permission": [r"\b403\b", r"PermissionError", r"role forbidden", r"not authori[sz]ed",
                   r"unauthori[sz]ed", r"forbidden"],
    "validation": [r"\b422\b", r"\b400\b", r"ValueError", r"invalid", r"out of range",
                   r"not in range", r"rejected", r"reject"],
    "comparison": [r"\b<\b", r"\b>\b", r"\bless than\b", r"\bgreater than\b", r"\bexceed",
                   r"\bat least\b", r"\bat most\b", r"boundary", r"limit",
                   r"min", r"max"],
    "arithmetic": [r"\bsum\b", r"\btotal\b", r"\bbalance\b", r"\binterest\b",
                   r"\bamount\b", r"\b==\b", r"assertEqual", r"assert .* =="],
    "other": [r"assert"],
}


def _suite_corpus(suite: dict[str, Any]) -> str:
    chunks: list[str] = []
    for t in suite.get("tests", []) or []:
        for key in ("name", "actions", "expected", "preconditions", "executable"):
            v = t.get(key)
            if isinstance(v, list):
                chunks.extend(str(x) for x in v)
            elif isinstance(v, str):
                chunks.append(v)
    return "\n".join(chunks).lower()


def kills_mutant(suite: dict[str, Any], mutant: Mutant) -> bool:
    hints = DETECTION_HINTS.get(mutant.behaviour_tag, DETECTION_HINTS["other"])
    corpus = _suite_corpus(suite)
    return any(re.search(h.lower(), corpus) for h in hints)


def score_suite(suite: dict[str, Any], mutants: list[Mutant]) -> MutationReport:
    killed = 0
    by_op: dict[str, list[int]] = {}
    for m in mutants:
        hit = kills_mutant(suite, m)
        killed += int(hit)
        stats = by_op.setdefault(m.op, [0, 0])
        stats[1] += 1
        stats[0] += int(hit)
    report = MutationReport(
        total=len(mutants), killed=killed,
        by_operator={op: (s[0], s[1]) for op, s in by_op.items()},
    )
    return report
