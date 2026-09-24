"""Stdlib-only Anthropic adapter.

Drop-in replacement for the anthropic-SDK-backed adapter, using only
Python's standard library (urllib + json). Useful in environments where
the anthropic pip package cannot be installed (offline build sandboxes,
corporate proxies, etc.). Callers see the same LLMResponse shape.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


@dataclass
class LLMResponse:
    text: str
    backend: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class StdlibAnthropicAdapter:
    def __init__(self, model: str = "claude-sonnet-4-6",
                 api_key: str | None = None,
                 max_retries: int = 6) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self.max_retries = max_retries

    def complete(self, prompt: str, *, max_output_tokens: int = 8000) -> LLMResponse:
        payload = json.dumps({
            "model": self.model,
            "max_tokens": max_output_tokens,
            # Deterministic decoding (see llm_adapter.AnthropicAdapter for
            # rationale). Keep parity between the two adapters so the cloud-job
            # behaviour does not depend on which one is selected.
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

        attempt = 0
        start = time.perf_counter()
        while True:
            attempt += 1
            req = urllib.request.Request(API_URL, method="POST",
                                         headers=headers, data=payload)
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    body = json.loads(r.read())
                    break
            except urllib.error.HTTPError as e:
                code = e.code
                is_transient = code in {429, 500, 502, 503, 529}
                if not is_transient or attempt >= self.max_retries:
                    raise
                delay = min(128, 2 ** (attempt + 1))
                print(f"[StdlibAnthropicAdapter] {code} transient; "
                      f"retry {attempt}/{self.max_retries} in {delay}s")
                time.sleep(delay)
            except urllib.error.URLError as e:
                if attempt >= self.max_retries:
                    raise
                delay = min(128, 2 ** (attempt + 1))
                print(f"[StdlibAnthropicAdapter] network error; "
                      f"retry {attempt}/{self.max_retries} in {delay}s: {e}")
                time.sleep(delay)

        latency_ms = int((time.perf_counter() - start) * 1000)
        text = "".join(
            block.get("text", "") for block in body.get("content", [])
            if block.get("type") == "text"
        )
        usage = body.get("usage", {})
        return LLMResponse(
            text=text,
            backend="anthropic-stdlib",
            model=self.model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            latency_ms=latency_ms,
            metadata={"stop_reason": body.get("stop_reason")},
        )
