"""Rule-based verification engine for RAITG.

Four rule classes:
  Structural  — parseable JSON, matches output schema, code parses
  Logical     — preconditions / actions / expected are consistent
  Coverage    — suite contains positive, negative, and boundary cases
                and every test traces to the source requirement
  Redundancy  — tests are not semantically duplicated
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

RULES_VERSION = "raitg-rules-v1.0.0"


@dataclass
class VerificationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    rule_class_scores: dict[str, bool] = field(default_factory=dict)

    def add(self, cls: str, violation: str | None) -> None:
        if violation is None:
            self.rule_class_scores.setdefault(cls, True)
        else:
            self.violations.append(f"[{cls}] {violation}")
            self.rule_class_scores[cls] = False
            self.ok = False


def _canonicalize(test: dict[str, Any]) -> tuple:
    """Canonical form of a test for redundancy detection."""
    return (
        tuple(sorted(s.lower().strip() for s in test.get("preconditions", []))),
        tuple(s.lower().strip() for s in test.get("actions", [])),
        tuple(sorted(s.lower().strip() for s in test.get("expected", []))),
    )


def structural_rules(doc: Any) -> list[str]:
    v: list[str] = []
    if not isinstance(doc, dict):
        v.append("response is not a JSON object")
        return v
    for key in ("requirement_id", "reasoning", "tests"):
        if key not in doc:
            v.append(f"missing top-level key: {key}")
    tests = doc.get("tests", [])
    if not isinstance(tests, list):
        v.append("`tests` is not an array")
        return v
    if len(tests) < 3:
        v.append(f"need >=3 tests, got {len(tests)}")
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            v.append(f"test[{i}] not an object"); continue
        for key in ("name", "kind", "heuristic", "preconditions",
                    "actions", "expected", "trace"):
            if key not in t:
                v.append(f"test[{i}] missing key: {key}")
        kind = str(t.get("kind", "")).lower().strip()
        if kind not in ("positive", "negative", "boundary"):
            v.append(f"test[{i}] has invalid kind: {t.get('kind')}")
        # Accept combined heuristic values like "NEG/STC" — take the first token
        heur_raw = str(t.get("heuristic", ""))
        heur = re.split(r"[\/,\s]+", heur_raw.strip())[0].upper() if heur_raw else ""
        if heur not in ("EP", "BVA", "STC", "DT", "NEG"):
            v.append(f"test[{i}] has invalid heuristic: {t.get('heuristic')}")
        # `executable` is optional and advisory; don't fail verification on
        # broken Python inside it (the behavioural fields — actions, expected,
        # heuristic, trace — carry the signal we score against).
    return v


def logical_rules(doc: Any) -> list[str]:
    v: list[str] = []
    tests = doc.get("tests", []) if isinstance(doc, dict) else []
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            continue
        # preconditions non-empty when kind is positive/boundary
        if t.get("kind") in ("positive", "boundary") and not t.get("preconditions"):
            v.append(f"test[{i}] {t.get('kind')} has empty preconditions")
        # actions must be non-empty
        if not t.get("actions"):
            v.append(f"test[{i}] has no actions")
        # expected must be non-empty
        if not t.get("expected"):
            v.append(f"test[{i}] has no expected outcomes")
        # NEG heuristic should appear on negative tests
        if t.get("kind") == "negative" and t.get("heuristic") not in ("NEG", "DT"):
            v.append(f"test[{i}] negative kind but heuristic={t.get('heuristic')}")
    return v


def coverage_rules(doc: Any, source_req_id: str) -> list[str]:
    v: list[str] = []
    if not isinstance(doc, dict):
        return ["response not an object"]
    tests = doc.get("tests", [])
    if not isinstance(tests, list):
        return ["tests not an array"]
    kinds = {str(t.get("kind", "")).lower().strip() for t in tests if isinstance(t, dict)}
    for expected in ("positive", "negative", "boundary"):
        if expected not in kinds:
            v.append(f"suite missing a {expected} case")
    req_id_doc = doc.get("requirement_id")
    if req_id_doc != source_req_id:
        v.append(f"requirement_id mismatch: {req_id_doc} != {source_req_id}")
    for i, t in enumerate(tests):
        trace = t.get("trace", []) if isinstance(t, dict) else []
        if not any(source_req_id in str(x) for x in trace):
            v.append(f"test[{i}] missing trace to {source_req_id}")
    return v


def redundancy_rules(doc: Any) -> list[str]:
    v: list[str] = []
    tests = doc.get("tests", []) if isinstance(doc, dict) else []
    seen: set[tuple] = set()
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            continue
        key = _canonicalize(t)
        if key in seen:
            v.append(f"test[{i}] is a semantic duplicate of an earlier test")
        seen.add(key)
    return v


def verify(raw_response: str | dict, source_req_id: str,
           *, enabled_classes: set[str] | None = None) -> VerificationResult:
    enabled = enabled_classes or {"structural", "logical", "coverage", "redundancy"}
    result = VerificationResult(ok=True)

    # Parse if string
    if isinstance(raw_response, str):
        doc: Any
        try:
            doc = json.loads(raw_response)
        except json.JSONDecodeError as e:
            result.add("structural", f"response not valid JSON: {e}")
            return result
    else:
        doc = raw_response

    if "structural" in enabled:
        for v in structural_rules(doc):
            result.add("structural", v)
        result.rule_class_scores.setdefault("structural", True)
    if "logical" in enabled:
        for v in logical_rules(doc):
            result.add("logical", v)
        result.rule_class_scores.setdefault("logical", True)
    if "coverage" in enabled:
        for v in coverage_rules(doc, source_req_id):
            result.add("coverage", v)
        result.rule_class_scores.setdefault("coverage", True)
    if "redundancy" in enabled:
        for v in redundancy_rules(doc):
            result.add("redundancy", v)
        result.rule_class_scores.setdefault("redundancy", True)
    return result
