"""Synthetic Gemini schema and error tests; no API key or network required."""
import io
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError

from inbody_mvp.gemini_review import (
    Extraction, extract_gemini, gemini_api_error_message,
)


def _synthetic_png():
    image = Image.new("RGB", (100, 60), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _install_fake_sdk(monkeypatch, generate):
    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    types.GenerateContentConfig = lambda **kwargs: kwargs
    genai.types = types
    genai.Client = lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=generate)
    )
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", types)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")


def test_extraction_sends_json_schema_without_openapi_additional_properties(monkeypatch):
    def generate_content(**kwargs):
        config = kwargs["config"]
        assert "response_json_schema" in config
        assert "response_schema" not in config
        assert config["response_mime_type"] == "application/json"
        assert config["response_json_schema"] == Extraction.model_json_schema()
        assert config["response_json_schema"]["additionalProperties"] is False
        return SimpleNamespace(text=json.dumps({
            "header": {
                "person_id": "000123",
                "exam_datetime": "2026-10-04 10:04:00",
                "age": 34,
            },
            "measurements": [{
                "section": "InBody Score",
                "measurement": "InBody Score",
                "value": "83",
                "unit": "points",
            }, {
                "section": "Segmental Lean Analysis",
                "measurement": "Right Arm - Lean Mass",
                "value": "8.20",
                "unit": "kg",
            }],
            "missing_or_unreadable": [],
        }))
    _install_fake_sdk(monkeypatch, generate_content)
    frame, snapshot, status = extract_gemini({
        "filename": "synthetic.png", "data": _synthetic_png()
    }, consent=True)
    assert len(frame) == 2
    assert frame.iloc[1]["value"] == "8.20"
    assert frame.iloc[1]["original_value"] == "8.20"
    assert snapshot["header"]["person_id"] == "000123"
    assert "2 mediciones" in status


def test_pydantic_still_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        Extraction.model_validate({
            "header": {
                "person_id": "000123",
                "exam_datetime": "2026-10-04 10:04:00",
                "age": 34,
                "unexpected": True,
            },
            "measurements": [],
            "missing_or_unreadable": [],
        })


@pytest.mark.parametrize("code,needle", [
    (400, "esquema JSON"),
    (401, "GEMINI_API_KEY"),
    (403, "Acceso denegado"),
    (404, "GEMINI_MODEL"),
    (429, "Cuota"),
    (503, "temporalmente"),
])
def test_safe_http_error_reporting(code, needle):
    result = gemini_api_error_message(code)
    assert f"HTTP {code}" in result
    assert needle in result


def test_no_raw_provider_error_is_exposed(monkeypatch):
    class ClientError(Exception):
        pass
    ClientError.__module__ = "google.genai.errors"
    def generate_content(**kwargs):
        error = ClientError("private-document-data-and-API-key")
        error.code = 400
        raise error
    _install_fake_sdk(monkeypatch, generate_content)
    with pytest.raises(Exception, match="HTTP 400") as caught:
        extract_gemini({
            "filename": "synthetic.png", "data": _synthetic_png()
        }, consent=True)
    assert "private-document-data-and-API-key" not in str(caught.value)
