"""Keep tests independent of the developer's selected live provider in .env."""

import pytest


@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch):
    monkeypatch.setenv("SOCIETY_LLM_PROVIDER", "openai")
