"""QA del guardado anónimo y consentimiento (sin conectar a Neon)."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inbody_mvp import demo_storage
from inbody_mvp.storage import ConfirmedExam


ROOT = Path(__file__).resolve().parents[1]


def make_report():
    return ConfirmedExam.model_validate({
        "id_persona": "CEDULA-PRIVADA-123",
        "modelo_inbody": "InBody 580",
        "timestamp": "2026-10-31T12:34:56",
        "edad": 34,
        "age_source": "test",
        "idioma_reporte": "ES",
        "source_sha256": "a" * 64,
        "source_type": "jpg",
        "measurements": [
            {
                "original_label": "PERSONAL-PII",
                "variable_medida": "weight",
                "unidad_medida": "kg",
                "valor_medida": 74.3,
                "segmento": None,
            },
            {
                "original_label": "OCR PRIVATE",
                "variable_medida": "unrecognized_free_text",
                "unidad_medida": "personal",
                "valor_medida": 25,
            },
        ],
    })


def test_demo_off_by_default_and_requires_separate_secret(monkeypatch):
    monkeypatch.delenv("ENABLE_ANONYMOUS_DEMO", raising=False)
    monkeypatch.setenv("DEMO_DATABASE_URL", "postgresql://fake:fake@host/db?sslmode=require")
    assert not demo_storage.anonymous_demo_enabled()
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.delenv("DEMO_DATABASE_URL", raising=False)
    assert not demo_storage.anonymous_demo_enabled()


def test_demo_consent_required_without_db_access(monkeypatch):
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.setenv("DEMO_DATABASE_URL", "postgresql://fake:fake@host/db?sslmode=require")
    with pytest.raises(PermissionError, match="aceptar el almacenamiento"):
        demo_storage.save_demo_exam(
            make_report(), storage_consent=False, publish_consent=True,
            anonymous_alias=str(uuid4()),
        )


def test_demo_only_writes_anonymized_approved_values(monkeypatch):
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.setenv("DEMO_DATABASE_URL", "postgresql://demo:fake@host/db?sslmode=require")
    queries = []

    class FakeConnection:
        def execute(self, sql, params):
            queries.append((str(sql), params))
            return SimpleNamespace(scalar_one=lambda: uuid4())

    class FakeTx:
        def __enter__(self):
            return FakeConnection()
        def __exit__(self, *_):
            return False

    class FakeEngine:
        def begin(self):
            return FakeTx()
        def dispose(self):
            pass

    monkeypatch.setattr(demo_storage, "_demo_database_engine", FakeEngine)
    report = make_report()
    alias = str(uuid4())
    result = demo_storage.save_demo_exam(
        report, storage_consent=True, publish_consent=True,
        anonymous_alias=alias,
    )
    assert result
    assert len(queries) == 1
    sql, params = queries[0]
    assert "hj_submit_demo_report" in sql
    assert params["alias"] == alias
    assert params["exam_date"] == "2026-10-31"
    assert params["publish"] is True
    measures = json.loads(params["measurements"])
    assert measures == [{
        "metric": "weight", "unit": "kg", "segment": None,
        "frequency_khz": None, "value": 74.3,
    }]
    combined = sql + json.dumps(params)
    for secret in ("CEDULA-PRIVADA-123", "PERSONAL-PII", "OCR PRIVATE", "a"*64):
        assert secret not in combined
    assert not {"age", "edad", "id_persona", "source_sha256", "raw_ocr"} & set(params)
    assert not {"age", "edad", "id_persona", "original_label"} & set(measures[0])


def test_demo_publish_opt_out_is_not_public(monkeypatch):
    monkeypatch.setenv("ENABLE_ANONYMOUS_DEMO", "1")
    monkeypatch.setenv("DEMO_DATABASE_URL", "fake")
    monkeypatch.setattr(demo_storage, "_demo_database_engine",
                        lambda: SimpleNamespace(begin=lambda: _Tx(), dispose=lambda: None))
    capture = []
    class _Conn:
        def execute(self, sql, params):
            capture.append(params)
            return SimpleNamespace(scalar_one=lambda: uuid4())
    class _Tx:
        def __enter__(self):
            return _Conn()
        def __exit__(self, *_):
            return False
    demo_storage.save_demo_exam(make_report(), storage_consent=True,
                                publish_consent=False, anonymous_alias=str(uuid4()))
    assert capture[0]["publish"] is False


def test_public_demo_view_and_database_role_are_restricted():
    migration = (ROOT / "db/migrations/004_anonymous_consented_demo.sql").read_text()
    assert "WHERE e.publish_approved IS TRUE" in migration
    assert "AND e.expires_at > now()" in migration
    assert "SECURITY DEFINER" in migration
    assert "SET search_path = pg_catalog, pg_temp" in migration
    assert "FROM PUBLIC" in migration and "GRANT EXECUTE" in migration
    assert "hj_demo_public_series" in migration
    # Access is restricted to demo objects, not to private patient tables.
    assert "INSERT INTO public.hj_persons" not in migration
    assert "INSERT INTO public.hj_exams" not in migration
    assert "FROM public.hj_measurements" not in migration


def test_gemini_audit_uses_restricted_demo_writer_without_legacy_demo_callback():
    app = (ROOT / "app.py").read_text()
    gemini = (ROOT / "inbody_mvp/gemini_review.py").read_text()
    assert "session_db_consent = gr.Checkbox(" in app
    assert "inputs=[gemini_table, gemini_snapshot, session_db_consent, gemini_overwrite]" in app
    assert "save_audit" in app
    assert "save_demo_exam" not in gemini
    assert "hj_submit_reviewed_audit" in gemini
    assert "DEMO_DATABASE_URL" in gemini
    assert "require_database_access(profile)" not in gemini
