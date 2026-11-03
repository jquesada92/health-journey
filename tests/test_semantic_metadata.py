"""Neon semantic glossary tests: synthetic labels only, no database access."""
from pathlib import Path

import pytest
from sqlalchemy.exc import ProgrammingError

from inbody_mvp import semantic_metadata as sem

ROOT = Path(__file__).resolve().parents[1]


class FakeConnection:
    def __init__(self, aliases, fields, fail=False):
        self.aliases = aliases
        self.fields = fields
        self.fail = fail
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if self.fail:
            raise ProgrammingError(sql, {}, Exception("relation does not exist"))
        rows = self.aliases if "hj_measurement_aliases" in sql else self.fields
        return self.Result(rows)

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self

        def all(self):
            return self.rows


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection
        self.disposed = False

    def connect(self):
        class Context:
            def __enter__(nested):
                return self.connection

            def __exit__(nested, *_):
                return False
        return Context()

    def dispose(self):
        self.disposed = True


def _metric(alias="phase angle", code="phase_angle"):
    return {
        "alias_normalized": alias, "canonical_code": code,
        "display_label_es": "Ángulo de fase", "canonical_unit": "°",
        "descripcion_medida": "Medida eléctrica bioimpedancia",
        "comparability_rule": "Mismo segmento, frecuencia y equipo",
        "interpretation_guidance": "Usar tendencia",
        "limitations": "No diagnosticar salud celular",
    }


def _field(name="weight"):
    return {
        "source_table": "hj_training_sets", "field_name": name,
        "display_label_es": "Carga", "description_es": "Carga del ejercicio",
        "unit_hint": "weight_unit",
        "interpretation_note": "No confundir con peso corporal",
    }


def test_metadata_for_selected_measures_only_no_personal_data(monkeypatch):
    connection = FakeConnection([_metric(), _metric("fat mass", "body_fat_mass")],
                                [_field()])
    engine = FakeEngine(connection)
    monkeypatch.setattr(sem, "_database_engine", lambda: engine)
    result = sem.load_coach_semantics(["Left Arm - Phase Angle"])
    assert result["available"] is True
    assert [m["code"] for m in result["metric_definitions"]] == ["phase_angle"]
    assert result["metric_definitions"][0]["limitations"] == "No diagnosticar salud celular"
    assert result["field_definitions"][0]["field"] == "weight"
    assert "owner_key" not in str(result)
    assert "anonymous_id" not in str(result)
    assert "IN (" in connection.queries[1]
    assert "exposed_to_ai IS TRUE" in connection.queries[1]
    assert engine.disposed


@pytest.mark.parametrize("label,expected", [
    ("Right Arm - Impedance at 100 kHz", "impedance"),
    ("Left Leg - Fat Mass", "fat mass"),
    ("Trunk - ECW Ratio", "ecw ratio"),
    ("Ángulo de fase", "angulo de fase"),
])
def test_segmental_suffix_and_accent_normalization(label, expected):
    assert sem._lookup_key(label) == expected


def test_db_missing_metadata_degrades_without_contacting_ai(monkeypatch):
    connection = FakeConnection([], [], fail=True)
    engine = FakeEngine(connection)
    monkeypatch.setattr(sem, "_database_engine", lambda: engine)
    output = sem.load_coach_semantics(["Weight"])
    assert output["available"] is False
    assert output["metric_definitions"] == []
    assert "no disponible" in output["note"]
    assert engine.disposed


def test_schema_migration_is_additive_private_and_preserves_existing_catalog():
    migration = (ROOT / "migrations/009_ai_semantic_metadata.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS public.hj_measurement_aliases" in migration
    assert "CREATE TABLE IF NOT EXISTS public.hj_ai_field_dictionary" in migration
    assert "ALTER TABLE public.hj_measurement_catalog ADD COLUMN IF NOT EXISTS" in migration
    assert "COMMENT ON TABLE public.hj_training_sets" in migration
    assert "COMMENT ON COLUMN public.hj_measurement_audits.final_value" in migration
    assert "COMMENT ON COLUMN public.hj_training_sets.owner_key" in migration
    assert "REVOKE ALL ON public.hj_measurement_aliases" in migration
    assert "GRANT SELECT ON public.hj_measurement_aliases" in migration
    assert "TO health_journey_app, health_journey_runtime" in migration
    assert "ON CONFLICT (canonical_code) DO UPDATE" in migration
    assert "ON CONFLICT (alias_normalized) DO NOTHING" in migration
    assert "DELETE FROM" not in migration
    assert "DROP TABLE" not in migration
    assert "TRUNCATE" not in migration
    assert "UPDATE public.hj_training_sets" not in migration


def test_semantics_loaded_after_private_inbody_and_training_read():
    source = (ROOT / "inbody_mvp/ai_coach.py").read_text()
    assert "person_id = resolve_private_person_id(" in source
    assert "inbody = load_reviewed_audit_history(" in source
    assert "training = _load_training(" in source
    assert "semantics = load_coach_semantics(" in source
    assert source.index("training = _load_training(") < source.index(
        "semantics = load_coach_semantics("
    )
    assert '"semantic_metadata": semantics' in source
    deployed = (ROOT / ".github/workflows/deploy-huggingface.yml").read_text()
    assert "'inbody_mvp/semantic_metadata.py'" in deployed
