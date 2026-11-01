"""Regresiones del inicio de sesión HF fuera de la vista incrustada.

No usa claves ni abre navegador: verifica enlaces seguros, configuración
existente y que la protección SQL continúe en el backend.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from inbody_mvp.oauth_ui import standalone_oauth_urls

ROOT = Path(__file__).resolve().parents[1]


def test_first_party_login_routes_from_space_host():
    urls = standalone_oauth_urls("jaqo-health-journey.hf.space")
    assert urls == {
        "app": "https://jaqo-health-journey.hf.space/",
        "login": "https://jaqo-health-journey.hf.space/login/huggingface",
        "logout": "https://jaqo-health-journey.hf.space/logout",
    }


def test_uses_original_hf_host_when_list_contains_custom_domain():
    urls = standalone_oauth_urls(
        "custom.example.com, jaqo-health-journey.hf.space"
    )
    assert urls is not None
    assert urls["app"] == "https://jaqo-health-journey.hf.space/"


@pytest.mark.parametrize("untrusted", [
    None,
    "",
    "https://jaqo-health-journey.hf.space",
    "https://evil.example",
    "evil.example",
    "jaqo-health-journey.hf.space/attacker",
    "jaqo-health-journey.hf.space?x=1",
    "jaqo-health-journey.hf.space@evil.example",
    "jaqo-health-journey.hf.space<script>",
])
def test_no_untrusted_redirects(untrusted):
    assert standalone_oauth_urls(untrusted) is None


def test_gradio_has_direct_login_and_oauth_stays_protected():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    storage = (ROOT / "inbody_mvp/storage.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    tree = ast.parse(app)
    assert any(
        isinstance(node, ast.Name) and node.id == "OAUTH_URLS"
        for node in ast.walk(tree)
    )
    assert "target=\"_blank\"" in app
    assert "OAUTH_URLS[\"login\"]" in app
    assert "hj_submit_reviewed_audit" in (ROOT / "inbody_mvp/gemini_review.py").read_text()
    assert "hf_oauth: true" in readme
    assert "gradio[oauth]" in requirements
    assert "require_database_access(profile)" in app
    assert 'getattr(oauth_profile, "username", None)' in storage


def test_deploy_includes_oauth_helper():
    workflow = (ROOT / ".github/workflows/deploy-huggingface.yml").read_text(
        encoding="utf-8"
    )
    assert "'inbody_mvp/oauth_ui.py'" in workflow
