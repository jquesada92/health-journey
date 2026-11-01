"""Gemini 503 failover tests; no actual API calls or documents."""
import io
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image

from inbody_mvp.gemini_review import (
    _fallback_model, _is_gemini_overloaded, extract_gemini,
)


def sample_upload():
    image = Image.new("RGB", (70, 50), "white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return {"filename": "synthetic.png", "data": buf.getvalue()}


def fake_sdk(monkeypatch, callback):
    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    types.GenerateContentConfig = lambda **config: config
    genai.Client = lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=callback)
    )
    genai.types = types
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", types)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-api-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)


def api_error(code):
    class ServerError(Exception):
        pass
    ServerError.__module__ = "google.genai.errors"
    err = ServerError("PRIVATE REQUEST MUST NOT BE SHOWN")
    err.code = code
    return err


def response():
    return SimpleNamespace(text=json.dumps({
        "header": {
            "person_id": "000123",
            "exam_datetime": "2026-10-04 10:04:00",
            "age": 34,
        },
        "measurements": [{
            "section": "Análisis Magro Segmental",
            "measurement": "Brazo derecho - Masa magra",
            "value": "8.20",
            "unit": "kg",
        }],
        "missing_or_unreadable": [],
    }))


def test_only_503_causes_one_model_failover(monkeypatch):
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise api_error(503)
        return response()
    fake_sdk(monkeypatch, generate_content)
    table, audit, message = extract_gemini(sample_upload(), consent=True)
    assert calls == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    assert table.iloc[0]["original_value"] == "8.20"
    assert audit["model"] == "gemini-3.5-flash-lite"
    assert audit["primary_model"] == "gemini-3.8-flash"
    assert audit["fallback_used"] is True
    assert "3.5-flash-lite" in message


def test_non_503_does_not_failover(monkeypatch):
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        raise api_error(429)
    fake_sdk(monkeypatch, generate_content)
    with pytest.raises(Exception, match="HTTP 429"):
        extract_gemini(sample_upload(), consent=True)
    assert calls == ["gemini-3.8-flash"]


def test_disabled_fallback_does_not_send_second_request(monkeypatch):
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        raise api_error(503)
    fake_sdk(monkeypatch, generate_content)
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "off")
    with pytest.raises(Exception, match="HTTP 503"):
        extract_gemini(sample_upload(), consent=True)
    assert calls == ["gemini-3.8-flash"]


def test_custom_fallback_is_used(monkeypatch):
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise api_error(503)
        return response()
    fake_sdk(monkeypatch, generate_content)
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-3.6-flash")
    _, audit, _ = extract_gemini(sample_upload(), consent=True)
    assert calls == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert audit["model"] == "gemini-3.6-flash"


def test_no_retry_when_same_model(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")
    assert _fallback_model("gemini-3.8-flash") is None


def test_api_error_classification():
    assert _is_gemini_overloaded(api_error(503))
    assert not _is_gemini_overloaded(api_error(429))
    assert not _is_gemini_overloaded(ValueError("bad data"))
