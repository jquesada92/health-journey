"""Explicit, private InBody re-upload and atomic same-filename replacement.

All records are synthetic. SQL mutation is checked statically; no live Neon
records are deleted or altered by these tests.
"""
import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from inbody_mvp import gemini_review as audit, upload_preflight as preflight
from inbody_mvp import storage, coach_data

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
MIGRATION = (ROOT / "migrations/010_private_inbody_filename_replace.sql").read_text()


def _synthetic():
    row = {
        "exam_datetime": "2025-01-26 14:20:00", "filename": "sample.pdf",
        "person_id": "00077", "age": 33, "section": "Body",
        "measurement": "Weight", "value": "75.20", "unit": "kg",
        "original_value": "75.20", "was_corrected": False,
        "correction_comment": "", "reviewed": True,
    }
    snapshot = {
        "sha256": hashlib.sha256(b"example input").hexdigest(),
        "filename": "sample.pdf", "model": "synthetic",
        "raw_response": json.dumps({"header": {}, "measurements": []}),
        "header": {
            "person_id": "00077", "exam_datetime": "2025-01-26 14:20:00",
            "age": 33,
        },
        "rows": [deepcopy(row)],
    }
    return pd.DataFrame([row], columns=audit.COLUMNS), snapshot


class PrivateEngine:
    def __init__(self, result=None):
        self.queries = []
        self.disposed = False
        self.result = result or {
            "status": "replaced_filename", "removed_measurements": 3,
            "inserted_measurements": 1,
        }

    def begin(self):
        engine = self
        class Tx:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def execute(self, statement, params):
                engine.queries.append((str(statement), params))
                return SimpleNamespace(scalar_one=lambda: engine.result)
        return Tx()

    def dispose(self):
        self.disposed = True


def _authorized(monkeypatch, *, person="00077"):
    allowed = []
    def grant(*, oauth_profile=None, request=None):
        allowed.append((oauth_profile, request))
    monkeypatch.setattr(storage, "require_database_access", grant)
    monkeypatch.setattr(
        coach_data, "resolve_private_person_id",
        lambda **kwargs: person,
    )
    monkeypatch.setattr(
        audit, "_audit_write_engine",
        lambda: pytest.fail("The demo writer must never replace files"),
    )
    private = PrivateEngine()
    monkeypatch.setattr(storage, "_database_engine", lambda: private)
    return private, allowed


def test_private_replacement_preserves_rereviewed_audit_and_not_demo_writer(monkeypatch):
    table, snapshot = _synthetic()
    table.at[0, "value"] = "75.30"
    table.at[0, "correction_comment"] = "Corregido al comparar el PDF"
    engine, allowed = _authorized(monkeypatch)
    msg = audit.save_audit(
        table, snapshot, consent=True, replace_filename=True,
        profile=SimpleNamespace(username="synthetic"),
        request=SimpleNamespace(token="signed"),
    )
    assert "Guardado en Neon" in msg
    assert "Se reemplazaron 3 registros" in msg
    assert len(engine.queries) == 1
    query, args = engine.queries[0]
    assert "hj_replace_reviewed_audit_filename" in query
    assert "hj_submit_reviewed_audit_receipt" not in query
    assert args["confirmed"] is True
    payload = json.loads(args["payload"])
    assert payload["filename"] == "sample.pdf"
    assert payload["measurements"][0]["value"] == "75.30"
    assert payload["measurements"][0]["original_value"] == "75.20"
    assert payload["measurements"][0]["was_corrected"] is True
    assert engine.disposed
    assert len(allowed) == 1


def test_replacement_rejects_cross_person_before_opening_database(monkeypatch):
    table, snapshot = _synthetic()
    engine, _ = _authorized(monkeypatch, person="another-owner")
    with pytest.raises(Exception, match="identificador"):
        audit.save_audit(table, snapshot, consent=True, replace_filename=True)
    assert not engine.queries


def test_replacement_rejects_unreviewed_or_unsigned_before_access(monkeypatch):
    table, snapshot = _synthetic()
    engine, _ = _authorized(monkeypatch)
    table.at[0, "reviewed"] = False
    with pytest.raises(Exception):
        audit.save_audit(table, snapshot, consent=True, replace_filename=True)
    with pytest.raises(Exception, match="autorizar"):
        audit.save_audit(table, snapshot, consent=False, replace_filename=True)
    assert not engine.queries


def test_existing_standard_writer_path_is_unchanged(monkeypatch):
    table, snapshot = _synthetic()
    engine, _ = _authorized(monkeypatch)
    monkeypatch.setattr(audit, "audit_write_enabled", lambda: True)
    demo = PrivateEngine({"status": "saved"})
    monkeypatch.setattr(audit, "_audit_write_engine", lambda: demo)
    msg = audit.save_audit(table, snapshot, consent=True)
    assert msg.startswith("Guardado en Neon:")
    assert len(demo.queries) == 1
    assert "hj_submit_reviewed_audit_receipt" in demo.queries[0][0]
    assert not engine.queries


def test_preflight_requires_private_ownership_before_gemini(monkeypatch):
    state = {"filename": "sample.pdf", "data": b"test"}
    calls = []
    monkeypatch.setattr(storage, "require_database_access", lambda **kw: calls.append("auth"))
    monkeypatch.setattr(coach_data, "resolve_private_person_id", lambda **kw: "00077")
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, statement, args):
            assert "hj_extraction_audits" in str(statement)
            assert "hj_person_aliases" in str(statement)
            assert args["person_id"] == "00077"
            assert args["filename"] == "sample.pdf"
            calls.append("lookup")
            return SimpleNamespace(scalar_one=lambda: True)
    class Engine:
        def connect(self): return Connection()
        def dispose(self): calls.append("dispose")
    monkeypatch.setattr(storage, "_database_engine", Engine)
    assert preflight.assert_private_filename_replacement(state) is None
    assert calls == ["auth", "lookup", "dispose"]


def test_filename_not_owned_rejects_reprocessing(monkeypatch):
    state = {"filename": "other-user.pdf", "data": b"test"}
    monkeypatch.setattr(storage, "require_database_access", lambda **kw: None)
    monkeypatch.setattr(coach_data, "resolve_private_person_id", lambda **kw: "00077")
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): return SimpleNamespace(scalar_one=lambda: False)
    class Engine:
        def connect(self): return Connection()
        def dispose(self): pass
    monkeypatch.setattr(storage, "_database_engine", Engine)
    with pytest.raises(PermissionError, match="no pertenece"):
        preflight.assert_private_filename_replacement(state)


def test_user_interface_opt_in_blocks_duplicate_by_default():
    assert 'gemini_replace_existing = gr.Checkbox(' in APP
    assert '"Reprocesar y reemplazar el archivo existente en Neon"' in APP
    assert "gemini_replace_existing.change(" in APP
    assert "assert_private_filename_replacement(" in APP
    assert "replace_filename" in APP
    assert "gemini_overwrite, gemini_replace_existing," in APP
    assert "gemini_upload_preflight," in APP
    assert "if replace_existing is not True:" in APP
    assert "status == \"duplicate\" and replace_existing is True" in APP
    assert "gemini_replace_existing," in APP
    tree = ast.parse(APP)
    extraction = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef)
                      and n.name == "extract_with_popup")
    body = ast.unparse(extraction)
    assert body.index("assert_private_filename_replacement(") < body.index(
        "extract_gemini("
    )
    assert "preflight_processed_upload(" in body
    assert "has_consent(request, 'ai')" in body


def test_migration_restricted_and_transactional_including_backup():
    assert "CREATE TABLE IF NOT EXISTS public.hj_replaced_audit_backups" in MIGRATION
    assert "CREATE OR REPLACE FUNCTION public.hj_replace_reviewed_audit_filename" in MIGRATION
    assert "SECURITY DEFINER" in MIGRATION
    assert "p_confirm_replace IS DISTINCT FROM true" in MIGRATION
    assert "p.normalized_person_id = v_person_key" in MIGRATION
    assert "lower(btrim(e.filename)) = lower(v_filename)" in MIGRATION
    assert "old_extraction" in MIGRATION
    assert "old_measurements" in MIGRATION
    assert "DELETE FROM public.hj_measurement_audits" in MIGRATION
    assert "DELETE FROM public.hj_extraction_audits" in MIGRATION
    assert MIGRATION.index("INSERT INTO public.hj_replaced_audit_backups") < MIGRATION.index(
        "DELETE FROM public.hj_measurement_audits"
    ) < MIGRATION.index("v_new_id := public.hj_submit_reviewed_audit")
    assert "REVOKE ALL ON FUNCTION public.hj_replace_reviewed_audit_filename" in MIGRATION
    assert "FROM health_journey_demo_writer" in MIGRATION
    assert "TO health_journey_app, health_journey_runtime" in MIGRATION
    assert "pg_advisory_xact_lock" in MIGRATION


def test_public_view_and_existing_audit_tables_are_not_redefined():
    assert "CREATE OR REPLACE VIEW" not in MIGRATION
    assert "ALTER TABLE public.hj_measurement_audits" not in MIGRATION
    assert "TRUNCATE" not in MIGRATION.upper()
