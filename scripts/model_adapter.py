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


class AdapterError(RuntimeError):
    """Raised when a model adapter cannot return a valid response."""


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
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key()}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise AdapterError(f"provider returned HTTP {exc.code}: {detail}") from exc
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterError(f"provider request failed: {exc}") from exc

        choices = payload.get("choices") or []
        if not choices:
            raise AdapterError("provider response contained no choices")
        choice = choices[0]
        content = (choice.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
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
