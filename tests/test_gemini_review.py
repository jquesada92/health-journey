"""Synthetic-only tests for opt-in Gemini and graceful Paddle fallback."""
from __future__ import annotations

from io import BytesIO
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image

from inbody_mvp import gemini_review, section_review


def synthetic_image() -> bytes:
    target = BytesIO()
    Image.new("RGB", (400, 600), "white").save(target, "PNG")
    return target.getvalue()


def test_gemini_never_calls_provider_without_explicit_consent(monkeypatch):
    monkeypatch.setenv("ENABLE_GEMINI_REVIEW", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    with pytest.raises(PermissionError, match="autorizar"):
        gemini_review.review_with_gemini("test.png", synthetic_image(), consent=False)


def test_gemini_disabled_by_default_even_with_consent(monkeypatch):
    monkeypatch.delenv("ENABLE_GEMINI_REVIEW", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    with pytest.raises(RuntimeError, match="no está habilitada"):
        gemini_review.review_with_gemini("test.png", synthetic_image(), consent=True)


def test_gemini_requires_configured_secret(monkeypatch):
    monkeypatch.setenv("ENABLE_GEMINI_REVIEW", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_review.review_with_gemini("test.png", synthetic_image(), consent=True)


def test_gemini_preserves_printed_decimals_and_excludes_history(monkeypatch):
    monkeypatch.setenv("ENABLE_GEMINI_REVIEW", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    sent = []
    schema_response = {
        "measurements": [
            {"section": "Impedancia", "variable": "Brazo derecho 50 kHz",
             "segment": "brazo derecho", "raw_value": "8.20", "unit": "ohm",
             "page": 1, "evidence": "Brazo derecho 8.20 ohm"},
            {"section": "Historial", "variable": "Peso", "segment": None,
             "raw_value": "70.0", "unit": "kg", "page": 1,
             "evidence": "Peso 70.0"},
            {"section": "Otro", "variable": "Inválido", "segment": None,
             "raw_value": "sin lectura", "unit": None, "page": 1,
             "evidence": "texto"},
        ]
    }

    class FakePart:
        @staticmethod
        def from_bytes(*, data, mime_type):
            sent.append((len(data), mime_type))
            return "image"

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeModels:
        def generate_content(self, **kwargs):
            sent.append(kwargs)
            return SimpleNamespace(text=json.dumps(schema_response))

    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    types.Part = FakePart
    types.GenerateContentConfig = FakeConfig
    genai.types = types
    genai.Client = lambda api_key: SimpleNamespace(models=FakeModels())
    google.genai = genai
    for name, module in [
        ("google", google), ("google.genai", genai),
        ("google.genai.types", types),
    ]:
        monkeypatch.setitem(sys.modules, name, module)

    result = gemini_review.review_with_gemini(
        "inventado.png", synthetic_image(), consent=True,
    )
    assert len(result) == 1
    assert result[0][3] == "8.20"  # not 8 or 8.2: preserve printed text
    assert result[0][4] == "ohm"
    assert sent[0][1] == "image/png"
    assert sent[1]["model"] == "gemini-2.5-flash"


def test_section_detection_failure_still_allows_manual_review(monkeypatch):
    monkeypatch.setattr(
        section_review, "ai_detect_layout",
        lambda _: (_ for _ in ()).throw(RuntimeError("private path / IDs")),
    )
    rows, metadata = section_review.propose_regions(
        "inventado.png", synthetic_image(),
    )
    assert metadata["layout_mode"] == "manual"
    assert len(rows) == 2
    assert rows[0][1] == "header" and rows[0][6] is True
    assert rows[1][1] == "other" and rows[1][6] is False
    assert "private" not in str(metadata)
