"""Regression for equivalent InBody IDs and pseudonymous audit queries."""
from pathlib import Path
from types import SimpleNamespace
from datetime import date
import re

import pytest

from inbody_mvp import storage

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("raw,expected", [
    ("88571257", "88571257"),
    ("8-857-1257", "88571257"),
    ("8 - 857 - 1257", "88571257"),
    ("0088571257", "0088571257"),  # leading zeroes matter
    ("AB-123", "AB-123"),          # alphanumeric punctuation is preserved
])
def test_canonicalizes_only_numeric_id_separators(raw, expected):
    assert storage.canonical_person_id(raw) == expected


@pytest.mark.parametrize("invalid", [None, "", "--", " " * 10])
def test_rejects_empty_numeric_id(invalid):
    with pytest.raises(ValueError):
        storage.canonical_person_id(invalid)


def test_private_query_emits_alias_but_no_original_person_id(monkeypatch):
    executed = []
    class Conn:
        def execute(self, statement, params):
            executed.append((str(statement), params))
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [{
                "anonymous_id": "abcd0000-1234-5678-9999-000000000000",
                "exam_date": date(2026, 10, 4),
                "section": "Body Composition Analysis",
                "measurement": "Weight",
                "value": "75.0",
                "unit": "kg",
                "was_corrected": False,
            }]))
    class Context:
        def __enter__(self):
            return Conn()
        def __exit__(self, *_):
            return False
    class Engine:
        def connect(self):
            return Context()
        def dispose(self):
            pass

    monkeypatch.setattr(storage, "require_database_access", lambda oauth_profile=None, request=None: None)
    monkeypatch.setattr(storage, "_database_engine", lambda: Engine())
    result = storage.load_reviewed_audit_history("8-857-1257")
    assert executed[0][1]["key"] == "88571257"
    assert "hj_audit_reviewed_private" in executed[0][0]
    assert "person_id" not in result[0]
    assert "filename" not in result[0]
    assert result[0]["value"] == "75.0"
    assert result[0]["anonymous_id"].startswith("abcd0000")


def test_private_auth_required_before_query(monkeypatch):
    def block(profile=None, request=None):
        raise PermissionError("access denied")
    monkeypatch.setattr(storage, "require_database_access", block)
    with pytest.raises(PermissionError):
        storage.load_reviewed_audit_history("88571257")


def test_private_view_schema_never_exposes_actual_id():
    migration = (ROOT / "migrations/005_consent_only_audit_writer.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS public.hj_person_aliases" in migration
    assert "normalized_person_id text PRIMARY KEY" in migration
    assert "anonymous_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE" in migration
    assert "'^[0-9[:space:]-]+$'" in migration
    assert "CREATE OR REPLACE VIEW public.hj_audit_reviewed_private" in migration
    view = migration.split("CREATE OR REPLACE VIEW public.hj_audit_reviewed_private", 1)[1]
    assert "SELECT e.anonymous_id" in view
    assert "e.person_id" not in view
    assert "e.filename" not in view
    assert "e.raw_response" not in view
    assert "TO health_journey_app, health_journey_runtime;" in view
    assert "REVOKE ALL ON public.hj_audit_reviewed_private FROM PUBLIC" in view


def test_dashboard_does_not_display_raw_id():
    app = (ROOT / "app.py").read_text()
    assert 'type="password"' in app
    assert "load_reviewed_audit_history(" in app
    start = app.index("def display_audit_history(")
    end = app.index("audit_button.click(", start)
    snippet = app[start:end]
    assert 'frame.iloc[0]["anonymous_id"][:8]' in snippet
    assert '"person_id"' not in snippet
    assert '"filename"' not in snippet
    assert "public_dashboard_enabled()" in app


def test_test_alias_requires_authorized_session_and_private_secret(monkeypatch):
    """Alias 'test' never bypasses private access checks."""
    monkeypatch.setenv("DASHBOARD_TEST_PERSON_ID", "1-234-5678")
    def reject(_profile, request=None):
        raise PermissionError("not authorized")
    monkeypatch.setattr(storage, "require_database_access", reject)
    monkeypatch.setattr(storage, "_database_engine", lambda: pytest.fail("No SQL before auth"))
    with pytest.raises(PermissionError):
        storage.load_reviewed_audit_history("test")


def test_test_alias_resolves_to_same_canonical_id_as_real_numeric_id(monkeypatch):
    """Mocked SQL checks that the alias maps server-side without response PII."""
    monkeypatch.setenv("DASHBOARD_TEST_PERSON_ID", "1-234-5678")
    monkeypatch.setattr(storage, "require_database_access", lambda profile=None, request=None: None)
    params_used = []
    class Connection:
        def execute(self, statement, params):
            params_used.append(params)
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [{
                "anonymous_id": "cafef00d-aaaa-4aaa-9aaa-000000000000",
                "exam_date": date(2026, 10, 4),
                "section": "Muscle-Fat Analysis",
                "measurement": "Weight",
                "value": "72.40",
                "unit": "kg",
                "was_corrected": False,
            }]))
    class DB:
        def __enter__(self): return Connection()
        def __exit__(self, *_): return False
    class Engine:
        def connect(self): return DB()
        def dispose(self): pass
    monkeypatch.setattr(storage, "_database_engine", Engine)
    result = storage.load_reviewed_audit_history("TeSt")
    assert params_used[0]["key"] == storage.canonical_person_id("1-234-5678")
    assert result[0]["anonymous_id"].startswith("cafef00d")
    assert "person_id" not in result[0]
    assert "filename" not in result[0]


def test_test_alias_requires_secret_even_for_authorized_user(monkeypatch):
    monkeypatch.delenv("DASHBOARD_TEST_PERSON_ID", raising=False)
    monkeypatch.setattr(storage, "require_database_access", lambda profile=None, request=None: None)
    monkeypatch.setattr(storage, "_database_engine", lambda: pytest.fail("No SQL without alias"))
    with pytest.raises(ValueError, match="DASHBOARD_TEST_PERSON_ID"):
        storage.load_reviewed_audit_history("test")
