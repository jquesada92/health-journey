"""Free-tier Gemini model discovery and manual selection, synthetic only."""
import io
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image

from inbody_mvp.gemini_review import (
    FREE_INBODY_FLASH_MODELS, free_model_options,
    get_free_inbody_models, extract_gemini, _fallback_model,
)


def _synthetic_image():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, format="PNG")
    return {"filename": "synthetic.png", "data": buffer.getvalue()}


def _fake_gemini(monkeypatch, names, callback=None):
    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    types.GenerateContentConfig = lambda **kwargs: kwargs
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if callback:
            return callback(kwargs)
        return SimpleNamespace(text=json.dumps({
            "header": {
                "person_id": "synthetic-id",
                "exam_datetime": "2026-10-05 12:00:00",
                "age": 30,
            },
            "measurements": [
                {"section": "InBody Score", "measurement": "InBody Score",
                 "value": "84", "unit": "points"}
            ],
            "missing_or_unreadable": [],
        }))
    genai.Client = lambda **kwargs: SimpleNamespace(models=SimpleNamespace(
        list=lambda: [
            SimpleNamespace(name="models/" + x, supported_actions=["generateContent"])
            for x in names
        ],
        generate_content=generate_content,
    ))
    genai.types = types
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", types)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    return calls


def test_only_documented_free_tier_flash_models_are_listed(monkeypatch):
    names = [
        "gemini-3.8-flash", "gemini-3.5-flash-lite",
        "gemini-4-argon", "gemini-3.8-flash-tts",
        "gemini-3-pro-preview", "gemini-3.1-flash-lite",
    ]
    _fake_gemini(monkeypatch, names)
    options = get_free_inbody_models()
    assert [value for label, value in options] == [
        "gemini-3.8-flash", "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]
    assert all("Free Tier" in label for label, _ in options)
    assert free_model_options([]) == []


def test_selection_is_passed_to_gemini_without_mutating_environment(monkeypatch):
    calls = _fake_gemini(monkeypatch, ["gemini-3.8-flash", "gemini-3.6-flash"])
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    _, snapshot, _ = extract_gemini(
        _synthetic_image(), consent=True, selected_model="gemini-3.6-flash"
    )
    assert calls == ["gemini-3.6-flash"]
    assert snapshot["model"] == "gemini-3.6-flash"
    assert snapshot["primary_model"] == "gemini-3.6-flash"
    assert snapshot["fallback_used"] is False


def test_paid_or_inappropriate_model_rejected_before_api_call(monkeypatch):
    calls = _fake_gemini(monkeypatch, ["gemini-4-argon"])
    with pytest.raises(Exception, match="Free Tier"):
        extract_gemini(
            _synthetic_image(), consent=True, selected_model="gemini-4-argon"
        )
    assert not calls
    assert "gemini-4-argon" not in FREE_INBODY_FLASH_MODELS


def test_invalid_configured_fallback_is_not_called(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-4-argon")
    assert _fallback_model("gemini-3.8-flash") is None


def test_model_lookup_requires_api_key_but_not_document(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_free_inbody_models()


def test_selector_ui_loads_reachable_models_and_never_uploads_document():
    from pathlib import Path
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert 'gemini_model_selector = gr.Dropdown(' in app
    assert 'get_free_inbody_models()' in app
    assert 'demo.load(' in app
    assert 'gemini_models_button.click(' in app
    assert 'extract_gemini(state, consent, selected_model=model)' in app
    assert 'inputs=[gemini_upload_state, gemini_consent_remote, gemini_model_selector]' in app
    assert 'fn=check_models_with_popup' in app
    assert 'choices=[], value=None' in app
    assert 'Free Tier tiene cuotas' in app
