"""Single-user fitness assistant reads authorized InBody and FitNotes data.

All data and identities are synthetic. No Neon or Gemini network calls.
"""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from inbody_mvp import ai_coach, coach_data


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return FakeResult(self.rows)


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def connect(self):
        class Context:
            def __enter__(inner):
                return self.connection

            def __exit__(inner, *_):
                return False
        return Context()

    def dispose(self):
        self.closed = True


def date_ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def test_no_visible_report_id_and_no_pii_in_prompt_source():
    assert "coach_report_id" not in APP
    assert 'label="Período de análisis (días)"' in APP
    assert "pend-ing" not in APP
    assert "pending, messages[:-1], None, goals" in APP
    assert "coach_goals, coach_restrictions, coach_window," in APP
    prompt = (ROOT / "inbody_mvp/prompts/fitness_coach.md").read_text()
    assert "`data.inbody_measurements.measurements`" in prompt
    assert "`data.training_sets.sets`" in prompt
    assert "No necesitas pedir un ID" in prompt
    assert "COACH_PERSON_ID" not in prompt


def test_secret_resolves_person_without_query_or_sending_id(monkeypatch):
    monkeypatch.setenv("COACH_PERSON_ID", "synthetic-owner")
    monkeypatch.setattr(coach_data, "require_database_access", lambda **kwargs: None)
    monkeypatch.setattr(coach_data, "_database_engine",
                        lambda: pytest.fail("No DB scan for pinned ID"))
    assert coach_data.resolve_private_person_id() == "synthetic-owner"


def test_single_person_discovery_and_multiple_person_fail_closed(monkeypatch):
    monkeypatch.delenv("COACH_PERSON_ID", raising=False)
    monkeypatch.delenv("DASHBOARD_TEST_PERSON_ID", raising=False)
    monkeypatch.setattr(coach_data, "require_database_access", lambda **kwargs: None)
    connection = FakeConnection(["synthetic-owner"])
    engine = FakeEngine(connection)
    monkeypatch.setattr(coach_data, "_database_engine", lambda: engine)
    assert coach_data.resolve_private_person_id() == "synthetic-owner"
    assert engine.closed is True
    assert "public.hj_person_aliases" in connection.calls[0][0]
    assert "public.hj_persons" in connection.calls[0][0]
    assert "LIMIT 2" in connection.calls[0][0]
    connection.rows = ["synthetic-owner", "another-person"]
    with pytest.raises(PermissionError, match="COACH_PERSON_ID"):
        coach_data.resolve_private_person_id()


def test_unauthorized_private_lookup_denied_even_when_secret_exists(monkeypatch):
    monkeypatch.setenv("COACH_PERSON_ID", "synthetic-owner")
    def reject(**kwargs):
        raise PermissionError("Sin acceso a Neon")
    monkeypatch.setattr(coach_data, "require_database_access", reject)
    with pytest.raises(PermissionError, match="Sin acceso"):
        coach_data.resolve_private_person_id()


def test_inbody_context_preserves_decimals_and_excludes_identifiers():
    data = coach_data.compact_inbody_rows([
        {
            "exam_date": date_ago(5), "section": "Composition",
            "measurement": "Fat Mass", "value": "-0.3700",
            "unit": "kg", "anonymous_id": "internal-uuid",
            "person_id": "synthetic-id", "filename": "synthetic.pdf",
            "correction_comment": "private comment", "raw_response": "raw",
        },
        {
            "exam_date": date_ago(500), "measurement": "Old",
            "value": "22.1", "unit": "kg",
        },
    ], days=90)
    assert data["measurements_available"] == 1
    assert data["measurements"][0]["value"] == "-0.3700"
    assert all(field not in str(data) for field in (
        "internal-uuid", "synthetic-id", "synthetic.pdf", "private comment", "raw",
    ))


def test_coach_reads_both_sources_with_no_typed_id(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_coach, "_owner_key", lambda **kwargs: "app:synthetic")
    monkeypatch.setattr(ai_coach, "resolve_private_person_id",
                        lambda **kwargs: "synthetic-id")

    def audit(person_id, **kwargs):
        calls.append(("inbody", person_id))
        return [{
            "exam_date": date_ago(7), "section": "Body",
            "measurement": "Weight", "unit": "kg", "value": "75.20",
        }]
    monkeypatch.setattr(ai_coach, "load_reviewed_audit_history", audit)
    monkeypatch.setattr(ai_coach, "load_measurement_history",
                        lambda *args, **kwargs: pytest.fail("Audit available"))
    monkeypatch.setattr(ai_coach, "_load_training", lambda owner, days: [{
        "exercise_key": "squat", "exercise": "Squat",
        "weight_unit": "kg", "workout_date": date_ago(1),
        "sets_count": 2, "reps_total": Decimal("15"),
        "max_weight": Decimal("90"), "volume": Decimal("1100"),
    }])
    def sets(owner, days):
        calls.append(("training", owner))
        return {"sets": [{
            "date": date_ago(1), "exercise": "Squat", "set": 1,
            "weight": "90", "weight_unit": "kg", "reps": "7",
        }], "truncated": False}
    monkeypatch.setattr(ai_coach, "load_private_training_sets", sets)
    # Generic semantic dictionary is read only after the private data gate.
    monkeypatch.setattr(ai_coach, "load_coach_semantics", lambda names: {
        "available": True, "metric_definitions": [{"code": "body_weight"}],
        "field_definitions": [], "truncated": False,
    })
    context = ai_coach.load_coach_context("ignored-client-id", days=90)
    assert calls == [("inbody", "synthetic-id"), ("training", "app:synthetic")]
    assert context["inbody"]["distinct_series"] == 1
    assert context["inbody_measurements"]["measurements"][0]["value"] == "75.20"
    assert context["training"]["sets_recorded"] == 2
    assert context["training_sets"]["sets"][0]["reps"] == "7"
    assert context["semantic_metadata"]["metric_definitions"][0]["code"] == "body_weight"
    assert "synthetic-id" not in str(context)
    assert "ignored-client-id" not in str(context)
    assert "app:synthetic" not in str(context)


def test_training_sets_owner_filter_and_private_fields_removed(monkeypatch):
    connection = FakeConnection([{
        "workout_date": date.fromisoformat(date_ago(2)),
        "exercise": "Squat", "category": "Legs", "set_number": 1,
        "weight": Decimal("105.00"), "weight_unit": "kg",
        "reps": Decimal("8"), "distance": None, "distance_unit": None,
        "duration_seconds": None,
        "comment": "Never pass to Gemini", "owner_key": "app:synthetic",
    }])
    monkeypatch.setattr(coach_data, "_database_engine", lambda: FakeEngine(connection))
    training = coach_data.load_private_training_sets("app:synthetic", days=90)
    assert training["sets"][0]["weight"] == "105.00"
    assert training["sets"][0]["reps"] == "8"
    assert "Never pass to Gemini" not in str(training)
    assert "app:synthetic" not in str(training)
    query, params = connection.calls[0]
    assert "owner_key = :owner" in query
    assert "comment" not in query.lower()
    assert params["owner"] == "app:synthetic"
    assert params["days"] == 90


def test_limited_detail_truthfully_reports_truncation(monkeypatch):
    dates = [{
        "exam_date": date_ago(1), "measurement": f"Metric {i}",
        "value": str(i), "unit": "kg",
    } for i in range(coach_data.MAX_INBODY_DETAIL + 1)]
    report = coach_data.compact_inbody_rows(dates, days=90)
    assert report["truncated"] is True
    assert report["measurements_available"] == coach_data.MAX_INBODY_DETAIL + 1
    assert len(report["measurements"]) == coach_data.MAX_INBODY_DETAIL
