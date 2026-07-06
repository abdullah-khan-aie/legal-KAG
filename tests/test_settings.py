from __future__ import annotations

import os

import pytest

from src.lodestone.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_load_with_required_neo4j_password(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("LODESTONE_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LODESTONE_NEO4J_PASSWORD", "test-secret")
    settings = Settings(_env_file=None)
    assert settings.bedrock_region == "eu-west-2"
    assert settings.llm_model == "anthropic.claude-sonnet-4-6"
    assert settings.embed_model == "cohere.embed-v4:0"
    assert settings.neo4j_password.get_secret_value() == "test-secret"
