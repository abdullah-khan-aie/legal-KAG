"""Outbound adapters that implement the model ports.

- OpenAICompatible* : real adapters (DeepSeek / OpenAI / Ollama / vLLM / ...),
  bound in bootstrap. They talk to YOUR model endpoint, never the OpenSPG server.
- Fake* : deterministic test doubles so the pipeline runs with no creds.

`httpx` is imported lazily so the fakes work even when it isn't installed.
"""

from __future__ import annotations

import json


class _OpenAIClient:
    """Shared config + POST helper for OpenAI-compatible HTTP endpoints."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        import httpx

        resp = httpx.post(
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


class OpenAICompatibleLanguageModel(_OpenAIClient):
    def complete(self, prompt: str, **kwargs) -> str:
        data = self._post(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        return data["choices"][0]["message"]["content"]


class OpenAICompatibleEmbeddingModel(_OpenAIClient):
    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post("/embeddings", {"model": self.model, "input": texts})
        return [item["embedding"] for item in data["data"]]


class FakeLanguageModel:
    """Returns canned NER/std/triple output keyed off the prompt type."""

    def complete(self, prompt: str, **kwargs) -> str:
        p = prompt.lower()
        if "entity extraction system" in p:
            return json.dumps(
                [
                    {"name": "Acme Corp", "category": "Company"},
                    {"name": "Globex", "category": "Company"},
                    {"name": "Delaware", "category": "GeographicLocation"},
                ]
            )
        if "official names" in p:
            return json.dumps(
                [
                    {
                        "name": "Acme Corp",
                        "category": "Company",
                        "official_name": "Acme Corporation",
                    },
                ]
            )
        if "openie" in p or "triples" in p:
            return json.dumps(
                {
                    "triples": [
                        ["Acme Corp", "entered into agreement with", "Globex"],
                        ["Acme Corp", "governed by", "Delaware"],
                    ]
                }
            )
        return "[]"


class FakeEmbeddingModel:
    def __init__(self, dim: int = 8):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[round((len(t) % 10) * 0.1, 3)] * self.dim for t in texts]
