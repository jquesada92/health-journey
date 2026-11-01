"""Model-selection and API diagnostic tests, without real Gemini credentials."""
from types import SimpleNamespace

import pytest

from inbody_mvp.gemini_review import (
    DEFAULT_GEMINI_MODEL,
    _model_name,
    available_flash_models,
)


def test_new_default_uses_current_flash(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"
    assert _model_name() == "gemini-3.8-flash"


def test_explicit_model_override_is_kept(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    assert _model_name() == "gemini-3.6-flash"


def test_list_only_flash_models_that_can_generate_content():
    data = [
        SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.6-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.5-flash-lite", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.1-flash-image", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.8-flash-tts", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["countTokens"]),
        SimpleNamespace(name="models/gemini-embedding-001", supported_actions=["embedContent"]),
    ]
    fake_client = SimpleNamespace(models=SimpleNamespace(list=lambda: iter(data)))
    assert available_flash_models(fake_client) == [
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
    ]


def test_no_available_model_returns_empty_list():
    client = SimpleNamespace(models=SimpleNamespace(list=lambda: iter([])))
    assert available_flash_models(client) == []
