"""Provider-neutral model adapter used by the blind-trial runner.

Only the adapter talks to a model.  The experiment runner, hashes, pairing and
raw-output storage remain provider-independent.  The default implementation is
Ollama's local HTTP API; cloud adapters can implement the same ``generate``
method without changing the experiment protocol.
"""

from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass


USER_AGENT = "RA-PSI-evaluator/1.0 (+https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026)"


class AdapterError(RuntimeError):
    """Raised when a model adapter cannot return a valid response.

    ``retry_after`` carries the provider's own wait hint, in seconds, when it
    sent one, so callers wait exactly as long as needed instead of guessing.
    """

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def parse_duration(value: str | None) -> float | None:
    """Read provider durations: "7.66s", "1m2.5s", "120ms", "30" (seconds)."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    total, number = 0.0, ""
    index = 0
    while index < len(text):
        char = text[index]
        if char.isdigit() or char == ".":
            number += char
            index += 1
            continue
        unit = "ms" if text.startswith("ms", index) else char
        if not number or unit not in ("ms", "h", "m", "s"):
            return None
        total += float(number) * {"ms": 0.001, "h": 3600, "m": 60, "s": 1}[unit]
        number = ""
        index += len(unit)
    return total if not number else None


def parse_rate_limit(headers) -> dict:
    """Extract what a provider says about its remaining capacity.

    Groq sends ``x-ratelimit-remaining-tokens`` and ``x-ratelimit-reset-tokens``;
    most gateways send ``retry-after`` on HTTP 429. Absent fields stay absent:
    the caller falls back to a fixed pause only when the provider said nothing.
    """
    if headers is None:
        return {}
    get = headers.get
    found = {}
    for key, name in (("remaining_tokens", "x-ratelimit-remaining-tokens"),
                      ("remaining_requests", "x-ratelimit-remaining-requests")):
        raw = get(name)
        if raw is not None:
            try:
                found[key] = int(float(raw))
            except ValueError:
                pass
    for key, name in (("reset_tokens_seconds", "x-ratelimit-reset-tokens"),
                      ("reset_requests_seconds", "x-ratelimit-reset-requests"),
                      ("retry_after_seconds", "retry-after")):
        seconds = parse_duration(get(name))
        if seconds is not None:
            found[key] = seconds
    return found


@dataclass(frozen=True)
class AdapterConfig:
    provider: str
    model: str
    endpoint: str = "http://127.0.0.1:11434/api/chat"
    temperature: float = 0.0
    max_output_tokens: int = 2048
    timeout_seconds: int = 300
    think: bool | None = False
    response_format: str | None = None
    # Provider-specific request fields, for example {"reasoning_effort": "low"}.
    extra_body: dict | None = None
    api_key_env: str = ""
    api_key_file: str = ""


class OllamaAdapter:
    """Small adapter for Ollama's local ``/api/chat`` endpoint."""

    def __init__(self, config: AdapterConfig):
        self.config = config

    def generate(self, prompt: str, seed: int) -> str:
        request_body = {
            "contract_version": "RA-PSI-MODEL-REQUEST-V1",
            "model": self.config.model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {
                "temperature": self.config.temperature,
                "seed": seed,
                "num_predict": self.config.max_output_tokens,
            },
        }
        # Reasoning models (qwen3, deepseek-r1, ...) route their chain of
        # thought to ``message.thinking`` and leave ``message.content`` empty
        # when the token budget is spent thinking.  The trial answer must be
        # the model's answer, so the thinking channel is disabled explicitly.
        if self.config.think is not None:
            request_body["think"] = self.config.think
        # Constrained decoding. Small models often emit several JSON values or
        # prose around them; asking Ollama for "json" makes the answer a single
        # parseable value. Unset by default so trial generation is untouched.
        if self.config.response_format is not None:
            request_body["format"] = self.config.response_format
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterError(f"Ollama request failed: {exc}") from exc

        message = payload.get("message", {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            thinking = message.get("thinking")
            if isinstance(thinking, str) and thinking.strip():
                raise AdapterError(
                    f"model {self.config.model!r} returned only a reasoning trace "
                    f"({len(thinking)} chars) and an empty message.content; "
                    "disable the thinking channel or raise max_output_tokens"
                )
            raise AdapterError("Ollama response did not contain non-empty message.content")
        # A budget-truncated answer is an experimenter artifact, not a model
        # answer: it never reaches the frozen results directory silently.
        if payload.get("done_reason") == "length":
            raise AdapterError(
                f"response truncated at max_output_tokens={self.config.max_output_tokens} "
                f"(eval_count={payload.get('eval_count')}); raise the budget and rerun this trial"
            )
        return content


class OpenAICompatibleAdapter:
    """Adapter for any OpenAI-compatible ``/chat/completions`` endpoint.

    DeepSeek, OpenRouter, Together and most hosted providers expose this same
    shape, so the experiment stays provider-neutral: only ``endpoint``,
    ``model`` and the API-key environment variable change.

    The key is read from the environment at call time.  It is never written to
    a file, a manifest, a raw output or a metadata record.
    """

    def __init__(self, config: AdapterConfig):
        self.config = config

    def _api_key(self) -> str:
        """Resolve the key from a file or the environment, at call time.

        The key is never returned to a caller that stores it, never written to
        a manifest, a raw output or a metadata record, and never included in an
        error message.  Keep the key file outside this tree: the public-safety
        scanner refuses secret-like files inside it.
        """
        path_name = self.config.api_key_file
        if path_name:
            path = os.path.expanduser(path_name)
            try:
                key = pathlib.Path(path).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise AdapterError(f"cannot read api key file {path}: {exc.strerror}") from exc
            if not key:
                raise AdapterError(f"api key file {path} is empty")
            return key
        name = self.config.api_key_env
        if not name:
            raise AdapterError(
                "an OpenAI-compatible provider needs --api-key-file or --api-key-env"
            )
        key = os.environ.get(name, "").strip()
        if not key:
            raise AdapterError(
                f"environment variable {name} is unset or empty; "
                "export it in the shell that runs the trials"
            )
        return key

    def generate(self, prompt: str, seed: int) -> str:
        request_body = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
            "stream": False,
            # Best-effort only: most hosted providers accept `seed` without
            # guaranteeing determinism.  The manifest records it as a pairing
            # label, not as a reproducibility guarantee.
            "seed": seed,
        }
        if self.config.response_format == "json":
            request_body["response_format"] = {"type": "json_object"}
        if self.config.extra_body:
            request_body.update(self.config.extra_body)
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key()}",
                # Some providers sit behind a firewall that rejects Python's
                # default User-Agent (Groq answers 403, Cloudflare error 1010).
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        self.last_rate_limit = {}
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                self.last_rate_limit = parse_rate_limit(response.headers)
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            limits = parse_rate_limit(exc.headers)
            self.last_rate_limit = limits
            raise AdapterError(f"provider returned HTTP {exc.code}: {detail}",
                               retry_after=limits.get("retry_after_seconds")) from exc
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterError(f"provider request failed: {exc}") from exc

        # The model that actually answered can differ from the one requested
        # (aliases, routers, silent upgrades). Provenance records the served one.
        self.last_served_model = str(payload.get("model") or self.config.model)
        choices = payload.get("choices") or []
        if not choices:
            # Gateways such as OpenRouter can return HTTP 200 with the real
            # failure in an "error" object; surface it instead of hiding it.
            error = payload.get("error")
            raise AdapterError(
                "provider response contained no choices: %s" % json.dumps(error)[:400]
                if error else "provider response contained no choices"
            )
        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            if message.get("reasoning"):
                raise AdapterError(
                    "model returned only reasoning and no answer; raise max_tokens or lower reasoning effort"
                )
            raise AdapterError("provider response did not contain non-empty message.content")
        if choice.get("finish_reason") == "length":
            raise AdapterError(
                f"response truncated at max_output_tokens={self.config.max_output_tokens}; "
                "raise the budget and rerun this trial"
            )
        return content


ADAPTERS = {
    "ollama": OllamaAdapter,
    "openai-compatible": OpenAICompatibleAdapter,
}


def build_adapter(config: AdapterConfig):
    """Return the adapter registered for ``config.provider``."""
    try:
        return ADAPTERS[config.provider](config)
    except KeyError:
        raise AdapterError(
            f"unknown provider {config.provider!r}; expected one of {sorted(ADAPTERS)}"
        ) from None
