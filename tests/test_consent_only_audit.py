"""Consent-only InBody audit, least-privilege SQL and Gradio UI contracts."""
from copy import deepcopy
from pathlib import Path
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from inbody_mvp import gemini_review as audit

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample():
    row = {
        "exam_datetime": "2026-10-04 10:04:00",
        "filename": "synthetic.png",
        "person_id": "000123",
        "age": 34,
        "section": "Body Composition Analysis",
        "measurement": "Total Body Water",
        "value": "8.20",
        "unit": "L",
        "original_value": "8.20",
        "was_corrected": False,
        "correction_comment": "",
        "reviewed": True,
    }
    snapshot = {
        "sha256": "a" * 64,
        "filename": "synthetic.png",
        "model": "synthetic-flash",
        "header": {"person_id": "000123", "exam_datetime": "2026-10-04 10:04:00", "age": 34},
        "raw_response": json.dumps({"header": {}, "measurements": []}),
        "rows": [deepcopy(row)],
    }
    return pd.DataFrame([row], columns=audit.COLUMNS), snapshot


def test_no_anonymous_write_without_restricted_role(monkeypatch):
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.setenv(
        "DEMO_DATABASE_URL",
        "postgresql://admin:fake@localhost/health_journey?sslmode=require",
    )
    assert not audit.audit_write_enabled()
    monkeypatch.setenv(
        "DEMO_DATABASE_URL",
        "postgresql://health_journey_demo_writer:fake@localhost/health_journey?sslmode=require",
    )
    assert audit.audit_write_enabled()
    monkeypatch.delenv("ENABLE_ANONYMOUS_DEMO")
    assert not audit.audit_write_enabled()


def test_removed_audit_flag_cannot_enable_anonymous_writes(monkeypatch):
    """The retired flag must not override ENABLE_ANONYMOUS_DEMO."""
    monkeypatch.delenv("ENABLE_ANONYMOUS_DEMO", raising=False)
    monkeypatch.setenv("ENABLE_ANONYMOUS_AUDIT", "1")
    monkeypatch.setenv(
        "DEMO_DATABASE_URL",
        "postgresql://health_journey_demo_writer:fake@localhost/health_journey?sslmode=require",
    )
    assert not audit.audit_write_enabled()
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    assert audit.audit_write_enabled()
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "0")
    assert not audit.audit_write_enabled()


def test_single_documented_feature_flag():
    example = (ROOT / ".env.example").read_text()
    module = (ROOT / "inbody_mvp/gemini_review.py").read_text()
    app = (ROOT / "app.py").read_text()
    assert "ENABLE_ANONYMOUS_AUDIT" not in example + module + app
    assert example.count("ENABLE_ANONYMOUS_DEMO=0") == 1
    assert "ENABLE_ANONYMOUS_DEMO" in module
    assert "ENABLE_ANONYMOUS_DEMO" in app


def test_consent_rejected_before_database_connection(monkeypatch, sample):
    monkeypatch.setattr(audit, "_audit_write_engine", lambda: pytest.fail("unexpected SQL"))
    with pytest.raises(Exception, match="autorizar"):
        audit.save_audit(*sample, consent=False, profile=None)


def test_consent_only_write_uses_function_and_preserves_original(monkeypatch, sample):
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.setenv(
        "DEMO_DATABASE_URL",
        "postgresql://health_journey_demo_writer:synthetic@host/health_journey?sslmode=require",
    )
    table, snapshot = sample
    table.at[0, "value"] = "8.02"
    table.at[0, "correction_comment"] = "Corrected the decimal from the document."
    submitted = []

    class Connection:
        def execute(self, query, params):
            submitted.append((str(query), json.loads(params["payload"])))
            return SimpleNamespace(scalar_one=lambda: {"status": "saved", "extraction_id": "synthetic-extraction-uuid"})

    class Tx:
        def __enter__(self):
            return Connection()
        def __exit__(self, *_):
            return False

    class Engine:
        def begin(self):
            return Tx()
        def dispose(self):
            pass

    monkeypatch.setattr(audit, "_audit_write_engine", Engine)
    result = audit.save_audit(table, snapshot, consent=True, profile=None)
    assert "Guardado en Neon" in result
    assert len(submitted) == 1
    query, payload = submitted[0]
    assert "hj_submit_reviewed_audit_receipt" in query
    assert "INSERT INTO" not in query
    assert payload["person_id"] == "000123"
    assert payload["measurements"][0]["original_value"] == "8.20"
    assert payload["measurements"][0]["value"] == "8.02"
    assert payload["measurements"][0]["was_corrected"] is True
    assert payload["measurements"][0]["correction_comment"].startswith("Corrected")
    assert payload["model_name"] == "synthetic-flash"


def test_duplicate_report_returns_idempotent_message(monkeypatch, sample):
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.setenv(
        "DEMO_DATABASE_URL",
        "postgresql://health_journey_demo_writer:fake@localhost/db?sslmode=require",
    )

    class Connection:
        def execute(self, statement, params):
            return SimpleNamespace(
                scalar_one=lambda: {"status": "filename_processed"}
            )
    class Engine:
        def begin(self):
            class Transaction:
                def __enter__(self): return Connection()
                def __exit__(self, *_): return False
            return Transaction()
        def dispose(self): pass
    monkeypatch.setattr(audit, "_audit_write_engine", Engine)
    status = audit.save_audit(*sample, consent=True)
    assert "ya fue procesado" in status
    assert "No se guardaron duplicados" in status
    assert "internal" not in status


def test_collision_requires_user_confirmation(monkeypatch, sample):
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.setenv(
        "DEMO_DATABASE_URL",
        "postgresql://health_journey_demo_writer:fake@localhost/db?sslmode=require",
    )
    calls = []
    class Connection:
        def execute(self, stmt, params):
            calls.append(params["confirm_overwrite"])
            return SimpleNamespace(scalar_one=lambda: (
                {"status": "overwritten", "conflicts": 1} if
                params["confirm_overwrite"] else
                {"status": "overwrite_required", "conflicts": 1}
            ))
    class Engine:
        def begin(self):
            class Tx:
                def __enter__(self): return Connection()
                def __exit__(self, *_): return False
            return Tx()
        def dispose(self): pass

    monkeypatch.setattr(audit, "_audit_write_engine", Engine)
    assert "Marca 'Confirmo sobrescribir" in audit.save_audit(*sample, consent=True)
    assert "Se actualizaron 1" in audit.save_audit(*sample, consent=True, confirm_overwrite=True)
    assert calls == [False, True]


def test_filename_checker_requires_private_auth(monkeypatch):
    from types import SimpleNamespace
    from inbody_mvp import storage
    def denied(profile=None, request=None):
        raise PermissionError("denied")
    monkeypatch.setattr(storage, "require_database_access", denied)
    monkeypatch.setattr(audit, "_audit_write_engine", lambda: pytest.fail("No DB"))
    message = audit.check_processed_filename({"filename": "test.pdf"})
    assert "inicia sesión" in message


def test_migration_reuses_existing_demo_role_without_private_table_grants():
    content = (ROOT / "migrations/005_consent_only_audit_writer.sql").read_text()
    assert "CREATE ROLE " not in content
    assert "SECURITY DEFINER" in content
    assert "REVOKE ALL ON FUNCTION public.hj_submit_reviewed_audit(jsonb) FROM PUBLIC" in content
    assert "GRANT EXECUTE ON FUNCTION public.hj_submit_reviewed_audit(jsonb)" in content
    assert "TO health_journey_demo_writer;" in content
    assert "REVOKE ALL ON public.hj_extraction_audits" in content
    assert "GRANT SELECT ON public.hj_person_aliases" in content
    assert "TO health_journey_app, health_journey_runtime;" in content
    assert "TO health_journey_demo_writer;" in content  # function EXECUTE only
    assert "GRANT SELECT ON public.hj_person_aliases TO health_journey_demo_writer" not in content
    assert "GRANT SELECT ON public.hj_audit_reviewed_private TO health_journey_public" not in content
    assert "REVOKE ALL ON public.hj_audit_reviewed_private FROM PUBLIC" in content


def test_both_consents_at_start_and_login_only_for_history():
    app = (ROOT / "app.py").read_text()
    start = app.index('with gr.Tab("InBody Upload")')
    end = app.index('with gr.Tab("Dashboard")', start)
    upload = app[start:end]
    # Session-wide opt-ins appear before any upload; no file can reset them.
    assert app.index("session_ai_consent = gr.Checkbox") < start
    assert app.index("session_db_consent = gr.Checkbox") < start
    assert "interactive=audit_write_enabled()" in upload
    assert "inputs=[gemini_table, gemini_snapshot, session_db_consent, gemini_overwrite]" in upload
    assert "inputs=[gemini_upload_state, session_ai_consent, gemini_model_selector]" in upload
    assert "inicia sesión en pestaña nueva" not in upload
    assert 'with gr.Tab("Historial en base de datos")' in app


def test_migration_007_requires_confirmation_and_keeps_history():
    migration = (ROOT / "migrations/007_idempotent_audit_save.sql").read_text()
    assert "hj_audit_filename_processed" in migration
    assert "hj_submit_reviewed_audit_receipt" in migration
    assert "'filename_processed'" in migration
    assert "'overwrite_required'" in migration
    assert "p_confirm_overwrite IS NOT TRUE" in migration
    assert "'overwritten'" in migration
    assert "dense_rank() OVER" in migration
    assert "version_rank = 1" in migration
    assert "DELETE FROM" not in migration
    assert "UPDATE public.hj_measurement_audits" not in migration
    assert "GRANT EXECUTE ON FUNCTION public.hj_submit_reviewed_audit_receipt" in migration
    assert "TO health_journey_demo_writer;" in migration


def test_review_ui_clears_only_after_success():
    source = (ROOT / "app.py").read_text()
    assert 'def save_review_and_clear(table, snapshot, consent, overwrite):' in source
    assert 'if message.startswith("Guardado en Neon:"):' in source
    assert "pd.DataFrame(columns=GEMINI_COLUMNS)" in source
    assert "gr.Info(visible_message)" in source
    assert "return keep_components(11)" in source
    assert "gemini_consent" not in source
    assert "gemini_upload.upload(" in source
    assert "gemini_upload.change(" not in source
    assert "gemini_overwrite = gr.Checkbox(" in source
    assert "fn=show_processed_filename" in source

