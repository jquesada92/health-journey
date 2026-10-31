"""Verificaciones sintéticas para la salida pública agregada.

Nunca se usan documentos reales ni una conexión de Neon.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from inbody_mvp import public_dashboard as subject


def test_public_endpoint_off_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_PUBLIC_DASHBOARD", raising=False)
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://fake:fake@localhost/db?sslmode=require")
    assert subject.public_dashboard_enabled() is False
    assert subject.load_public_monthly_summary() == []


def test_public_endpoint_requires_database_url(monkeypatch):
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.delenv("PUBLIC_DATABASE_URL", raising=False)
    assert subject.public_dashboard_enabled() is False
    assert subject.load_public_monthly_summary() == []


def test_public_metric_allowlist(monkeypatch):
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://fake:fake@localhost/db?sslmode=require")
    for candidate in ("id_persona", "birth_date", "sin_clasificar", "weight;DROP TABLE hj_persons;"):
        with pytest.raises(ValueError):
            subject.load_public_monthly_summary(candidate)


def test_public_records_only_use_approved_columns_and_cohorts(monkeypatch):
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://fake:fake@localhost/db?sslmode=require")
    executed = []
    class FakeConnect:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def execute(self, statement, params):
            executed.append((str(statement), dict(params)))
            good = {
                "period_month": date(2026, 7, 1),
                "device_group": "InBody 580",
                "variable_medida": "weight",
                "unidad_medida": "kg",
                "segmento": None,
                "frecuencia_khz": None,
                "participantes": 5,
                "valor_promedio": Decimal("71.21"),
                "person_uuid": "MUST-NOT-BE-EXPOSED",
                "id_persona": "MUST-NOT-BE-EXPOSED",
            }
            too_small = dict(good, participantes=4)
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [good, too_small]))
    class FakeEngine:
        def connect(self):
            return FakeConnect()
        def dispose(self):
            pass

    monkeypatch.setattr(subject, "_public_database_engine", lambda: FakeEngine())
    found = subject.load_public_monthly_summary("weight")
    assert len(found) == 1
    assert set(found[0]) == set(subject.PUBLIC_COLUMNS)
    assert found[0]["period_month"] == "2026-07-01"
    assert found[0]["valor_promedio"] == 71.21
    assert found[0]["participantes"] == 5
    assert executed[0][1] == {"variable": "weight", "row_limit": 120}
    # Public query must never reference private base tables, even indirectly.
    sql = executed[0][0].lower()
    assert "hj_public_monthly_summary" in sql
    for forbidden in ("hj_persons", "hj_exams", "hj_measurements_long", "original_label", "id_persona"):
        assert forbidden not in sql


def test_public_view_requires_explicit_approval_and_five_distinct_people():
    migration = (Path(__file__).resolve().parents[1] /
                 "db/migrations/002_public_aggregate_dashboard.sql").read_text(encoding="utf-8")
    assert "e.public_release_approved_at IS NOT NULL" in migration
    assert "HAVING COUNT(*) >= 5" in migration
    assert "e.person_uuid" in migration and "personal_monthly_mean" in migration
    assert "FROM hj_measurements_long" not in migration

def test_public_mode_denies_all_private_report_actions(monkeypatch):
    from inbody_mvp.storage import require_report_access, require_database_access
    monkeypatch.setenv("SPACE_ID", "jaqo/health-journey-public")
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.setenv("ENABLE_PERSISTENCE", "1")
    monkeypatch.setenv("HF_ALLOWED_USERS", "jaqo")
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "postgresql://fake:fake@localhost/db?sslmode=require")
    allowed_user = SimpleNamespace(username="jaqo", name="Some Name")
    for action in (require_report_access, require_database_access):
        with pytest.raises(PermissionError, match="solo publica estadísticas agregadas"):
            action(allowed_user)
        with pytest.raises(PermissionError, match="solo publica estadísticas agregadas"):
            action(None)
