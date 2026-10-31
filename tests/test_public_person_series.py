"""Pruebas sintéticas de publicación individual sin información de identidad."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from inbody_mvp import public_dashboard


def test_person_series_only_uses_anonymous_projection(monkeypatch):
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "configured-test-url")
    queried = []

    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def execute(self, query, params):
            queried.append((str(query), params))
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [{
                "anonymous_id": "c9365f26-7f88-4e81-a63b-e282220f3dbb",
                "exam_date": date(2026, 7, 14),
                "device_group": "InBody 580",
                "variable_medida": "weight",
                "unidad_medida": "kg",
                "segmento": None,
                "frecuencia_khz": None,
                "valor_medida": Decimal("73.2"),
                "id_persona": "SENSITIVE-ID-MUST-NOT-ESCAPE",
                "edad": 34,
                "birth_date": date(1990, 1, 1),
                "source_sha256": "secret-file-hash",
            }]))

    class Engine:
        def connect(self):
            return Connection()
        def dispose(self):
            pass

    monkeypatch.setattr(public_dashboard, "_public_database_engine", Engine)
    rows = public_dashboard.load_public_person_series("weight")
    assert len(rows) == 1
    assert set(rows[0]) == set(public_dashboard.PUBLIC_SERIES_COLUMNS)
    assert rows[0]["exam_date"] == "2026-07-14"
    assert rows[0]["valor_medida"] == 73.2
    assert queried[0][1]["metric"] == "weight"
    assert "FROM hj_public_person_series" in queried[0][0]
    assert "id_persona" not in queried[0][0]
    assert "hj_persons" not in queried[0][0]


def test_person_series_never_uses_private_db_and_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_PUBLIC_DASHBOARD", raising=False)
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "fake-url")
    assert public_dashboard.load_public_person_series("weight") == []
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.delenv("PUBLIC_DATABASE_URL")
    assert public_dashboard.load_public_person_series("weight") == []


def test_person_series_disallows_arbitrary_columns(monkeypatch):
    monkeypatch.setenv("ENABLE_PUBLIC_DASHBOARD", "1")
    monkeypatch.setenv("PUBLIC_DATABASE_URL", "fake-url")
    for metric in ("id_persona", "fecha_nacimiento", "original_label", "age"):
        with pytest.raises(ValueError):
            public_dashboard.load_public_person_series(metric)


def test_migration_only_releases_confirmed_opt_in_exams():
    sql = (Path(__file__).resolve().parents[1] /
           "db/migrations/003_public_pseudonymous_series.sql").read_text(encoding="utf-8")
    assert "DEFAULT gen_random_uuid()" in sql
    assert "e.public_release_approved_at IS NOT NULL" in sql
    assert "m.confirmation_status = 'confirmed'" in sql
    view_sql = sql.split("CREATE OR REPLACE VIEW hj_public_person_series", 1)[1].split("COMMENT ON VIEW", 1)[0]
    for forbidden in ("p.id_persona", "e.edad", "e.source_sha256", "original_label", "birth_date", "source_namespace"):
        assert forbidden not in view_sql
    assert "p.public_alias::text AS anonymous_id" in view_sql


def test_storage_opt_in_defaults_private():
    source = (Path(__file__).resolve().parents[1] /
              "inbody_mvp/storage.py").read_text(encoding="utf-8")
    assert "publish: bool = False" in source
    assert "CASE WHEN :publish THEN now() ELSE NULL END" in source
    assert "require_database_access(oauth_profile)" in source
