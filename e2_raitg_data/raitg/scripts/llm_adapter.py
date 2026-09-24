"""LLM backend adapters.

Current adapters:
  - AnthropicAdapter: Claude (Sonnet / Haiku / Opus)
  - OpenAIAdapter: GPT-4o-mini and other OpenAI chat models
  - GeminiAdapter: Google Gemini 2.5 Flash (and other Gemini models)
  - GroqAdapter: Groq-hosted Meta Llama 3.3 70B (and other Groq chat models)
  - DeterministicStubAdapter: offline replacement that returns plausible
    JSON responses for pipeline tests and for dry runs without an API key.
"""

from __future__ import annotations

import json
import os
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

try:  # optional dependency
    import anthropic  # type: ignore
except Exception:  # pragma: no cover
    anthropic = None  # type: ignore


@dataclass
class LLMResponse:
    text: str
    backend: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMAdapter(ABC):
    @abstractmethod
    def complete(self, prompt: str, *, max_output_tokens: int = 3000) -> LLMResponse:
        ...


class AnthropicAdapter(LLMAdapter):
    def __init__(self, model: str = "claude-sonnet-4-6",
                 api_key: str | None = None) -> None:
        if anthropic is None:
            raise RuntimeError(
                "anthropic SDK not installed. `pip install anthropic --break-system-packages`"
            )
        self.model = model
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    def complete(self, prompt: str, *, max_output_tokens: int = 8000) -> LLMResponse:
        start = time.perf_counter()
        # Retry on transient server errors with exponential backoff.
        transient_codes = {429, 500, 502, 503, 529}
        max_attempts = 6
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_output_tokens,
                    # Deterministic decoding: same prompt → same output. Without
                    # this the LLM picks different phrasings for the same
                    # requirement on each call, which makes pass-rate unstable
                    # (today: 14/14 → 2/8 between two consecutive runs of the
                    # same job). At 0 the only remaining variance is server-side.
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                status = getattr(e, "status_code", None)
                is_transient = status in transient_codes or "overloaded" in str(e).lower()
                if not is_transient or attempt >= max_attempts:
                    raise
                # Exponential backoff with jitter: 4s, 8s, 16s, 32s, 64s, 128s
                delay = min(128, 2 ** (attempt + 1))
                print(f"[AnthropicAdapter] transient error (status={status}); "
                      f"retry {attempt}/{max_attempts} in {delay}s: {e}")
                time.sleep(delay)
        latency_ms = int((time.perf_counter() - start) * 1000)
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(
            text=text,
            backend="anthropic",
            model=self.model,
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
            latency_ms=latency_ms,
            metadata={"stop_reason": getattr(resp, "stop_reason", None)},
        )


class OpenAIAdapter(LLMAdapter):
    """OpenAI chat-completion adapter (defaults to gpt-4o-mini).

    Matches the AnthropicAdapter shape: temperature=0 for deterministic
    decoding, same transient-error retry with exponential backoff. The
    ``seed`` argument (optional) is forwarded to the OpenAI API for
    reproducibility across runs; None means no explicit seed.
    """

    def __init__(self, model: str = "gpt-4o-mini",
                 api_key: str | None = None,
                 seed: int | None = None) -> None:
        try:
            import openai  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "openai SDK not installed. `pip install openai --break-system-packages`"
            ) from e
        self.model = model
        self.seed = seed
        self.client = openai.OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY")
        )

    def complete(self, prompt: str, *, max_output_tokens: int = 8000) -> LLMResponse:
        start = time.perf_counter()
        transient_codes = {429, 500, 502, 503}
        max_attempts = 6
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    # Deterministic decoding to match Sonnet baseline as
                    # closely as possible for the cross-provider comparison.
                    temperature=0,
                    # None = no seed; otherwise OpenAI attempts reproducibility.
                    seed=self.seed,
                    max_tokens=max_output_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                status = getattr(e, "status_code", None)
                is_transient = status in transient_codes or "overloaded" in str(e).lower()
                if not is_transient or attempt >= max_attempts:
                    raise
                delay = min(128, 2 ** (attempt + 1))
                print(f"[OpenAIAdapter] transient error (status={status}); "
                      f"retry {attempt}/{max_attempts} in {delay}s: {e}")
                time.sleep(delay)
        latency_ms = int((time.perf_counter() - start) * 1000)
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        return LLMResponse(
            text=text,
            backend="openai",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            metadata={
                "finish_reason": getattr(resp.choices[0], "finish_reason", None),
                "system_fingerprint": getattr(resp, "system_fingerprint", None),
                "seed": self.seed,
            },
        )


class GeminiAdapter(LLMAdapter):
    """Google Gemini adapter (defaults to gemini-2.5-flash).

    Supports either ``google-generativeai`` (legacy SDK) or ``google-genai``
    (new SDK) — whichever is installed. Note: the Gemini SDK does not
    expose a first-class ``seed`` argument in generation_config, so seed
    variance for reproducibility studies must be done on OpenAI only.
    """

    def __init__(self, model: str = "gemini-2.5-flash",
                 api_key: str | None = None) -> None:
        self.model = model
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        # Try legacy SDK first, fall back to new SDK
        self._impl = None
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=key)
            self._genai = genai
            self._model = genai.GenerativeModel(model)
            self._impl = "legacy"
        except Exception:
            try:
                from google import genai as _genai2  # type: ignore
                self._client = _genai2.Client(api_key=key)
                self._impl = "new"
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    "No Google Gemini SDK found. Install one of:\n"
                    "  pip install google-generativeai\n"
                    "  pip install google-genai"
                ) from e

    def complete(self, prompt: str, *, max_output_tokens: int = 8000) -> LLMResponse:
        start = time.perf_counter()
        transient_names = {"ResourceExhausted", "DeadlineExceeded",
                           "InternalServerError", "ServiceUnavailable"}
        max_attempts = 6
        attempt = 0
        while True:
            attempt += 1
            try:
                if self._impl == "legacy":
                    resp = self._model.generate_content(
                        prompt,
                        generation_config={
                            "temperature": 0,
                            "max_output_tokens": max_output_tokens,
                        },
                    )
                else:
                    resp = self._client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config={
                            "temperature": 0,
                            "max_output_tokens": max_output_tokens,
                        },
                    )
                break
            except Exception as e:
                name = type(e).__name__
                is_transient = (
                    name in transient_names
                    or "overloaded" in str(e).lower()
                    or "rate" in str(e).lower()
                )
                if not is_transient or attempt >= max_attempts:
                    raise
                delay = min(128, 2 ** (attempt + 1))
                print(f"[GeminiAdapter] transient error ({name}); "
                      f"retry {attempt}/{max_attempts} in {delay}s: {e}")
                time.sleep(delay)
        latency_ms = int((time.perf_counter() - start) * 1000)
        # ``response.text`` works on both SDKs for simple text output.
        text = getattr(resp, "text", "") or ""
        usage = getattr(resp, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
        return LLMResponse(
            text=text,
            backend="google",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            metadata={"sdk": self._impl},
        )


class GroqAdapter(LLMAdapter):
    """Groq chat-completion adapter (defaults to Meta Llama 3.3 70B versatile).

    Groq's Python SDK is drop-in compatible with the OpenAI chat.completions
    interface, so the shape here mirrors :class:`OpenAIAdapter`. The main
    difference is the free-tier rate limit (~30 requests/minute, ~6000/day),
    which motivates a slightly more generous exponential backoff on 429s.
    ``temperature=0`` matches the deterministic decoding used by the Sonnet
    baseline. ``seed`` is forwarded when non-None (Groq accepts the OpenAI
    seed parameter).
    """

    def __init__(self, model: str = "llama-3.3-70b-versatile",
                 api_key: str | None = None,
                 seed: int | None = None) -> None:
        try:
            import groq  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "groq SDK not installed. `pip install groq --break-system-packages`"
            ) from e
        self.model = model
        self.seed = seed
        self.client = groq.Groq(
            api_key=api_key or os.environ.get("GROQ_API_KEY")
        )

    def complete(self, prompt: str, *, max_output_tokens: int = 8000) -> LLMResponse:
        start = time.perf_counter()
        transient_codes = {429, 500, 502, 503}
        max_attempts = 6
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    # Deterministic decoding to match Sonnet baseline as
                    # closely as possible for the cross-provider comparison.
                    temperature=0,
                    seed=self.seed,
                    max_tokens=max_output_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                status = getattr(e, "status_code", None)
                is_transient = status in transient_codes or "rate" in str(e).lower()
                if not is_transient or attempt >= max_attempts:
                    raise
                # Same shape as OpenAI/Anthropic backoff: 4s, 8s, 16s, 32s,
                # 64s, 128s. Groq's free-tier limit is ~30 req/min, so
                # 429s should clear within one or two of these steps.
                delay = min(128, 2 ** (attempt + 1))
                print(f"[GroqAdapter] transient error (status={status}); "
                      f"retry {attempt}/{max_attempts} in {delay}s: {e}")
                time.sleep(delay)
        latency_ms = int((time.perf_counter() - start) * 1000)
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        return LLMResponse(
            text=text,
            backend="groq",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            metadata={
                "finish_reason": getattr(resp.choices[0], "finish_reason", None)
                                 if resp.choices else None,
                "seed": self.seed,
            },
        )


class DeterministicStubAdapter(LLMAdapter):
    """Deterministic stub for offline / CI runs.

    Produces a plausible RAITG-style JSON response for the requirement
    identified in the prompt. Does NOT call any external service.
    """

    def __init__(self, quality: float = 0.80) -> None:
        self.quality = quality
        self._rng = random.Random(42)

    def complete(self, prompt: str, *, max_output_tokens: int = 3000) -> LLMResponse:
        # Pull the requirement id out of the prompt
        req_id = "R-UNKNOWN"
        for line in prompt.splitlines():
            if line.startswith("Requirement ID:"):
                req_id = line.split(":", 1)[1].strip()
                break
        # "naive" mode uses plain text; here we always emit JSON
        is_naive = "[OUTPUT]" not in prompt
        if is_naive:
            body = (
                f"# tests for {req_id}\n"
                "def test_positive(): assert True\n"
                "def test_negative(): assert True\n"
                "def test_boundary(): assert True\n"
            )
            return LLMResponse(text=body, backend="stub", model="stub-naive",
                               input_tokens=len(prompt) // 4,
                               output_tokens=len(body) // 4,
                               latency_ms=10)

        # Occasionally drop a required field to simulate imperfect output
        drop_trace = self._rng.random() > self.quality

        tests = []
        for kind, heur in [("positive", "EP"), ("negative", "NEG"), ("boundary", "BVA")]:
            test = {
                "name": f"{kind}_case_{req_id}",
                "kind": kind,
                "heuristic": heur,
                "preconditions": ["system under test is available"],
                "actions": [f"invoke requirement {req_id} in {kind} mode"],
                "expected": [
                    "successful response" if kind == "positive" else "documented error"
                ],
                "trace": [] if drop_trace else [req_id],
                "executable": (
                    f"def test_{kind}_{req_id.replace('-','_').lower()}():\n"
                    f"    # stub test\n    assert True\n"
                ),
            }
            tests.append(test)

        doc = {
            "requirement_id": req_id,
            "reasoning": f"Applied heuristics to {req_id}.",
            "tests": tests,
        }
        text = json.dumps(doc)
        return LLMResponse(text=text, backend="stub", model="stub-raitg",
                           input_tokens=len(prompt) // 4,
                           output_tokens=len(text) // 4,
                           latency_ms=15)


def build_adapter(backend: str = "auto",
                  model: str = "claude-sonnet-4-6",
                  seed: int | None = None) -> LLMAdapter:
    backend = backend.lower()
    if backend == "stub":
        return DeterministicStubAdapter()
    if backend == "stdlib":
        from llm_adapter_stdlib import StdlibAnthropicAdapter  # type: ignore
        return StdlibAnthropicAdapter(model=model)  # type: ignore[return-value]

    if backend in ("openai", "gpt"):
        try:
            import openai  # type: ignore  # noqa: F401
            has_sdk = True
        except Exception:
            has_sdk = False
        has_key = bool(os.environ.get("OPENAI_API_KEY"))
        problems = []
        if not has_key:
            problems.append(
                "OPENAI_API_KEY env var is not set. "
                "Set it with: $env:OPENAI_API_KEY='sk-...' (PowerShell)"
            )
        if not has_sdk:
            problems.append(
                "openai SDK is not installed. Install it with: pip install openai"
            )
        if problems:
            raise RuntimeError(
                "OpenAI backend requested but unavailable:\n  - "
                + "\n  - ".join(problems)
            )
        return OpenAIAdapter(model=model, seed=seed)

    if backend in ("groq", "llama"):
        try:
            import groq  # type: ignore  # noqa: F401
            has_sdk = True
        except Exception:
            has_sdk = False
        has_key = bool(os.environ.get("GROQ_API_KEY"))
        problems = []
        if not has_key:
            problems.append(
                "GROQ_API_KEY env var is not set. "
                "Set it with: $env:GROQ_API_KEY='gsk_...' (PowerShell)"
            )
        if not has_sdk:
            problems.append(
                "groq SDK is not installed. Install it with: pip install groq"
            )
        if problems:
            raise RuntimeError(
                "Groq backend requested but unavailable:\n  - "
                + "\n  - ".join(problems)
            )
        return GroqAdapter(model=model, seed=seed)

    if backend in ("gemini", "google"):
        has_sdk = False
        try:
            import google.generativeai  # type: ignore  # noqa: F401
            has_sdk = True
        except Exception:
            try:
                from google import genai  # type: ignore  # noqa: F401
                has_sdk = True
            except Exception:
                has_sdk = False
        has_key = bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        )
        problems = []
        if not has_key:
            problems.append(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) env var is not set. "
                "Set it with: $env:GEMINI_API_KEY='...' (PowerShell)"
            )
        if not has_sdk:
            problems.append(
                "Google Gemini SDK is not installed. Install one of:\n"
                "      pip install google-generativeai\n"
                "      pip install google-genai"
            )
        if problems:
            raise RuntimeError(
                "Gemini backend requested but unavailable:\n  - "
                + "\n  - ".join(problems)
            )
        # NOTE: Gemini SDK has no first-class ``seed`` argument in
        # generation_config, so the seed parameter is intentionally ignored
        # here. Reproducibility variance studies use OpenAI only.
        return GeminiAdapter(model=model)

    if backend in ("auto", "anthropic", "claude"):
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_sdk = anthropic is not None
        if has_key and has_sdk:
            return AnthropicAdapter(model=model)
        if has_key and not has_sdk:
            from llm_adapter_stdlib import StdlibAnthropicAdapter  # type: ignore
            print("[llm_adapter] anthropic SDK absent — using stdlib adapter")
            return StdlibAnthropicAdapter(model=model)  # type: ignore[return-value]
        if backend == "auto":
            reason = []
            if not has_key: reason.append("ANTHROPIC_API_KEY not set")
            if not has_sdk: reason.append("anthropic SDK not installed")
            print(f"[llm_adapter] {'; '.join(reason)} — falling back to stub")
            return DeterministicStubAdapter()
        # Explicit backend request: be specific about what's missing
        problems = []
        if not has_key:
            problems.append(
                "ANTHROPIC_API_KEY env var is not set. "
                "Set it with: $env:ANTHROPIC_API_KEY='sk-ant-...' (PowerShell)"
            )
        if not has_sdk:
            problems.append(
                "anthropic SDK is not installed. "
                "Install it with: pip install anthropic"
            )
        raise RuntimeError(
            "Anthropic backend requested but unavailable:\n  - "
            + "\n  - ".join(problems)
        )
    raise ValueError(f"unknown backend: {backend}")
