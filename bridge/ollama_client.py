"""Small health client for the local Ollama service."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_seconds: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def list_models(self) -> list[str]:
        request = Request(self.base_url + "/api/tags", headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaUnavailable(f"Ollama is unavailable at {self.base_url}: {exc}") from exc
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise OllamaUnavailable("Ollama returned an invalid /api/tags response")
        return [str(item.get("name")) for item in models if isinstance(item, dict) and item.get("name")]

    def require_model(self, model: str) -> list[str]:
        models = self.list_models()
        if model not in models:
            raise OllamaUnavailable(f"Ollama model not installed: {model}; available={models}")
        return models
