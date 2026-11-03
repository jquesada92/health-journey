"""First + ten latest private InBody coach mini-trends (no external services)."""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from inbody_mvp import coach_trends

ROOT = Path(__file__).resolve().parents[1]


def rows_for_n_exams(n=16):
    first = date(2023, 1, 1)
    dates = [first + timedelta(days=30 * index) for index in range(n)]
    result = []
    for index, day in enumerate(dates):
        for section, name, unit, value in (
            ("Muscle-Fat Analysis", "Weight", "kg", Decimal("65.20") + index),
            ("Muscle-Fat Analysis", "Skeletal Muscle Mass", "kg",
             Decimal("30.10") + Decimal(index) / 10),
            ("Obesity Analysis", "Body Fat Percentage", "%",
             Decimal("19.50") - Decimal(index) / 10),
            ("InBody Score", "InBody Score", "points", Decimal("70") + index),
        ):
            result.append({
                "exam_date": day.isoformat(), "section": section,
                "measurement": name, "unit": unit,
                "value": str(value), "was_corrected": False,
            })
    return dates, result


@pytest.mark.parametrize("n,expected", [(1, 1), (3, 3), (10, 10), (11, 11),
                                         (16, 11), (25, 11)])
def test_first_and_ten_latest_no_duplicates_and_chronological(n, expected):
    dates, records = rows_for_n_exams(n)
    selected = coach_trends.first_and_last_ten_exam_dates(records)
    assert selected == sorted(set(dates[:1] + dates[-10:]))
    assert len(selected) == expected
    assert selected[0] == dates[0]
    assert selected[-1] == dates[-1]


def test_each_of_four_plots_uses_same_first_and_ten_last_dates_not_last_ten_only():
    dates, records = rows_for_n_exams(16)
    figs, count = coach_trends.render_coach_trend_figures(records)
    assert count == 11
    assert len(figs) == 4
    chosen = sorted(set(dates[:1] + dates[-10:]))
    for fig in figs:
        assert len(fig.data) == 1
        assert len(fig.data[0].x) == 11
        assert list(fig.data[0].x) == chosen
        assert fig.layout.height == 140
        assert len(fig.data[0].y) == 11
        assert all(x not in fig.data[0].x for x in dates[1:6])
    assert figs[0].data[0].y[0] == 65.2
    assert figs[3].data[0].y[-1] == 85.0


def test_same_date_rows_do_not_duplicate_points_or_inflate_count():
    dates, records = rows_for_n_exams(4)
    repeated = dict(records[0])
    repeated["value"] = "65.30"
    figures, count = coach_trends.render_coach_trend_figures(records + [repeated])
    assert count == 4
    assert len(figures[0].data[0].x) == 4


def test_missing_score_uses_empty_state_not_inferred_from_another_metric():
    dates, records = rows_for_n_exams(4)
    filtered = [r for r in records if r["measurement"] != "InBody Score"]
    figs, count = coach_trends.render_coach_trend_figures(filtered)
    assert count == 4
    assert len(figs[3].data) == 0
    assert "sin datos" in figs[3].layout.title.text.lower()
    assert len(figs[0].data[0].x) == 4


def test_spanish_aliases_and_metric_units():
    day = date(2025, 4, 2).isoformat()
    records = [
        {"exam_date": day, "section": "Análisis músculo-grasa",
         "measurement": "Peso", "unit": "kg", "value": "75.20"},
        {"exam_date": day, "section": "Análisis músculo-grasa",
         "measurement": "Masa Musculoesquelética", "unit": "kg", "value": "33.40"},
        {"exam_date": day, "section": "Obesidad",
         "measurement": "Porcentaje de grasa corporal", "unit": "%", "value": "20.30"},
        {"exam_date": day, "section": "InBody Score",
         "measurement": "Puntaje InBody", "unit": "puntos", "value": "80"},
    ]
    figures, count = coach_trends.render_coach_trend_figures(records)
    assert count == 1
    assert all(len(fig.data) == 1 for fig in figures)
    assert figures[0].data[0].y[0] == 75.2


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        class Result:
            def __init__(self, rows):
                self.rows = rows
            def mappings(self):
                return self
            def all(self):
                return self.rows
        return Result(self.rows.pop(0))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeEngine:
    def __init__(self, db):
        self.db = db
        self.disposed = False
    def connect(self):
        return self.db
    def dispose(self):
        self.disposed = True


def test_loader_authorizes_before_db_and_queries_first_plus_latest_at_sql_level(monkeypatch):
    calls = []
    monkeypatch.setattr(
        coach_trends, "require_database_access",
        lambda **kwargs: calls.append(("authorized", kwargs)),
    )
    monkeypatch.setattr(
        coach_trends, "resolve_private_person_id",
        lambda **kwargs: "synthetic-person",
    )
    db = FakeDB([[{
        "exam_date": date(2025, 3, 1), "section": "Body",
        "measurement": "Weight", "value": "76.20", "unit": "kg",
        "was_corrected": False, "person_id": "must_not_leak",
    }]])
    engine = FakeEngine(db)
    monkeypatch.setattr(coach_trends, "_database_engine", lambda: engine)
    profile = SimpleNamespace(username="synthetic")
    rows, source = coach_trends.load_private_coach_trend_rows(profile=profile)
    assert calls == [("authorized", {"oauth_profile": profile, "request": None})]
    assert source == "auditorías InBody revisadas"
    assert "must_not_leak" not in str(rows)
    assert engine.disposed
    query, params = db.calls[0]
    assert "JOIN public.hj_person_aliases p" in query
    assert "p.normalized_person_id = :person_key" in query
    assert "ORDER BY exam_date ASC LIMIT 1" in query
    assert "ORDER BY exam_date DESC LIMIT 10" in query
    assert "UNION" in query
    assert params["person_key"] == "SYNTHETIC-PERSON"


def test_denied_permission_never_queries_db(monkeypatch):
    def reject(**kwargs):
        raise PermissionError("No autorizado")
    monkeypatch.setattr(coach_trends, "require_database_access", reject)
    monkeypatch.setattr(
        coach_trends, "_database_engine",
        lambda: pytest.fail("Prohibited private database read"),
    )
    with pytest.raises(PermissionError):
        coach_trends.load_private_coach_trend_rows()


def test_legacy_confirmed_read_when_no_audited_rows(monkeypatch):
    monkeypatch.setattr(coach_trends, "require_database_access", lambda **kwargs: None)
    monkeypatch.setattr(coach_trends, "resolve_private_person_id",
                        lambda **kwargs: "111222")
    db = FakeDB([[], [{
        "exam_date": date(2024, 1, 1), "section": "Body",
        "measurement": "Weight", "value": Decimal("70.30"),
        "unit": "kg", "was_corrected": False,
    }]])
    monkeypatch.setattr(coach_trends, "_database_engine", lambda: FakeEngine(db))
    rows, source = coach_trends.load_private_coach_trend_rows()
    assert len(db.calls) == 2
    assert source == "mediciones InBody confirmadas"
    assert rows[0]["value"] == "70.30"
    assert "m.confirmation_status = 'confirmed'" in db.calls[1][0]


def test_responsive_left_panel_and_auto_refresh_in_gradio_app():
    app = (ROOT / "app.py").read_text()
    css = (ROOT / "inbody_mvp/coach_chat_ui.py").read_text()
    assert 'elem_id="hj-coach-layout"' in app
    assert 'elem_id="hj-coach-trends"' in app
    assert 'elem_id="hj-coach-conversation"' in app
    assert 'elem_id="hj-coach-mini-plots"' in app
    assert "for trigger in (nav_coach.click, coach_trend_refresh.click):" in app
    assert "outputs=[*coach_trend_plots, coach_trend_status]" in app
    assert "load_private_coach_trend_rows(" in app
    assert "render_coach_trend_figures(trend_rows)" in app
    assert "elem_id=\"hj-coach-chatbot\"" in app
    assert "#hj-coach-trends" in css
    assert "#hj-coach-layout" in css
    assert "max-height: 295px" in css
    workflow = (ROOT / ".github/workflows/deploy-huggingface.yml").read_text()
    assert "'inbody_mvp/coach_trends.py'" in workflow
