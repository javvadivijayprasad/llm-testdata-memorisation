"""Robust JSON extraction from LLM responses.

Handles the common cases where Claude (or any LLM) wraps a JSON object in:
  - triple-backtick code fences (```json ... ``` or ``` ... ```)
  - leading / trailing prose ("Here is the JSON:\n{...}\nLet me know...")
  - a single outer JSON array or object with extra whitespace

Returns a parsed Python object if a well-formed JSON object or array can be
located anywhere in the text; otherwise raises ``json.JSONDecodeError``.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(
    r"```(?:json|javascript|js)?\s*(?P<body>[\s\S]*?)```",
    re.IGNORECASE,
)


def _try_load(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _balanced_slice(text: str, open_ch: str, close_ch: str) -> str | None:
    """Return the first balanced {...} or [...] substring, or None."""
    start = text.find(open_ch)
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def extract_json(text: str) -> Any:
    """Extract the first JSON object or array from ``text``.

    Order of attempts:
      1. Parse the text as-is.
      2. Strip triple-backtick fences and try each fenced block.
      3. Balanced-slice the first ``{...}`` and the first ``[...]``.
    Raises ``json.JSONDecodeError`` if nothing parses.
    """
    if not text:
        raise json.JSONDecodeError("empty text", text or "", 0)

    # 1) direct
    parsed = _try_load(text.strip())
    if parsed is not None:
        return parsed

    # 2) fenced blocks
    for m in _FENCE_RE.finditer(text):
        body = m.group("body").strip()
        parsed = _try_load(body)
        if parsed is not None:
            return parsed

    # 3) balanced slicing
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        sliced = _balanced_slice(text, open_ch, close_ch)
        if sliced:
            parsed = _try_load(sliced)
            if parsed is not None:
                return parsed

    raise json.JSONDecodeError("could not locate valid JSON in response",
                               text[:200], 0)
