"""Regresiones del Space único: OCR, CSV, dashboard y Neon privado.

No carga imágenes reales ni inicia Gradio/EasyOCR. Comprueba la configuración
del código y los permisos de almacenamiento mediante fixtures sintéticos.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from inbody_mvp.public_dashboard import public_dashboard_enabled
from inbody_mvp.storage import database_enabled, require_database_access, require_report_access


ROOT = Path(__file__).resolve().parents[1]


def _assigned_widget(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return node.value
    raise AssertionError(f"Falta el widget {name}")


@pytest.mark.parametrize("widget", ["gemini_upload", "gemini_extract"])
def test_main_ui_controls_remain_enabled_when_public_dashboard_is_active(widget):
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    call = _assigned_widget(tree, widget)
    assert isinstance(call, ast.Call)
    interactive = next((k.value for k in call.keywords if k.arg == "interactive"), None)
    if widget == "gemini_extract":
        # The extractor starts disabled until its private duplicate preflight
        # completes. That is independent of ENABLE_PUBLIC_DASHBOARD.
        assert isinstance(interactive, ast.Constant) and interactive.value is False
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        assert 'interactive=status in {"new", "unverified"}' in source
        # Duplicate reports remain blocked without explicit private reprocess.
        # Both preflight and server extraction independently verify this.
        assert 'preflight.get("status") == "duplicate"' in source
        assert 'replace_existing is not True' in source
        assert 'if fresh["status"] == "duplicate":' in source
        assert 'assert_private_filename_replacement(' in source
    else:
        assert interactive is None or (
            isinstance(interactive, ast.Constant) and interactive.value is True
        ), f"{widget} no puede deshabilitarse al activar ENABLE_PUBLIC_DASHBOARD."


def test_combined_space_keeps_public_and_private_credentials_separate(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "jaqo/health-journey")
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://public:fake@host/db?sslmode=require")
    monkeypatch.setenv("DATABASE_URL", "postgresql://private:fake@host/db?sslmode=require")
    monkeypatch.setenv("ENABLE_PERSISTENCE", "1")
    monkeypatch.setenv("HF_ALLOWED_USERS", "jaqo")

    assert public_dashboard_enabled()
    assert database_enabled()
    require_report_access(None)
    require_report_access(SimpleNamespace(username="other"))
    for profile in (None, SimpleNamespace(username="other")):
        with pytest.raises(PermissionError):
            require_database_access(profile)
    require_database_access(SimpleNamespace(username="jaqo"))


def test_public_dashboard_without_private_database_still_allows_upload(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "jaqo/health-journey")
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://public:fake@host/db?sslmode=require")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ENABLE_PERSISTENCE", "0")

    assert public_dashboard_enabled()
    assert database_enabled() is False
    require_report_access(None)
    with pytest.raises(PermissionError):
        require_database_access(None)
