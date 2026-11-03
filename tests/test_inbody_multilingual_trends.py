"""Regression tests for multilingual InBody measurements and mixed units.

Only synthetic labels and dates are used; no medical data or Neon access.
"""
from datetime import date, timedelta
from decimal import Decimal

from inbody_mvp import coach_trends, progress_dashboard as dashboard


def _entry(exam, measurement, value, unit, section="Muscle-Fat Analysis"):
    return {
        "exam_date": exam.isoformat(),
        "measurement": measurement,
        "value": str(value),
        "unit": unit,
        "section": section,
        "was_corrected": False,
    }


def test_all_three_fat_percentage_labels_map_to_one_concept():
    # These names are all present in the reviewed-data schema.
    for name in (
        "Body Fat Percentage",
        "Percent Body Fat",
        "Percentage of Body Fat",
        "Porcentaje de grasa corporal",
        "Porcentaje Grasa Corporal",
    ):
        assert dashboard._base_metric(name) == "Body Fat Percentage"


def test_one_exam_every_month_with_alternating_name_keeps_all_selected_points():
    names = ("Body Fat Percentage", "Percent Body Fat", "Percentage of Body Fat")
    first = date(2024, 1, 1)
    entries = []
    dates = [first + timedelta(days=28 * n) for n in range(17)]
    for i, exam in enumerate(dates):
        label = names[i % 3]
        unit = ("%", "pct", "Porcentaje")[i % 3]
        entries.extend([
            _entry(exam, "Weight", "75.20", "KG"),
            _entry(exam, "Skeletal Muscle Mass", "34,30", "kilograms"),
            _entry(exam, label, Decimal("20.20") + Decimal(i) / 100,
                   unit, "Obesity Analysis"),
            _entry(exam, "InBody Score", 80 + i, "points", "InBody Score"),
        ])
    figures, count = coach_trends.render_coach_trend_figures(entries)
    assert count == 11
    assert len(figures) == 4
    expected_dates = sorted(set(dates[:1] + dates[-10:]))
    for fig in figures:
        assert list(fig.data[0].customdata) == [
            d.strftime("%d/%m/%Y") for d in expected_dates
        ]
        assert all(v is not None for v in fig.data[0].y)
    assert figures[2].data[0].y[0] == 20.2
    assert figures[2].layout.title.text.startswith("<b>Grasa corporal</b>")


def test_spanish_sections_metric_units_and_score_variants_are_supported():
    exam = date(2025, 10, 2)
    entries = [
        _entry(exam, "Peso corporal", "74,90", "kilogramos",
               "Análisis músculo-grasa"),
        _entry(exam, "Masa Musculoesquelética", "33.40", "KG",
               "Análisis músculo-grasa"),
        _entry(exam, "Porcentaje de grasa", "19.6", "percent",
               "Análisis de obesidad"),
        _entry(exam, "Puntaje", 81, "puntos", "Puntaje InBody"),
    ]
    figures, count = coach_trends.render_coach_trend_figures(entries)
    assert count == 1
    assert [f.data[0].y[0] for f in figures] == [74.9, 33.4, 19.6, 81.0]


def test_unambiguous_pounds_are_converted_only_in_chart_copy():
    exam = date(2025, 4, 3)
    original = _entry(exam, "Weight", "165.35", "lbs")
    rows = dashboard._normalize_records([original])
    output = dashboard._metric_points(rows, "Weight", "kg")
    assert len(output) == 1
    expected = Decimal("165.35") * Decimal("0.45359237")
    assert output[0]["numeric"] == expected
    assert output[0]["source_original"] == "165.35"
    assert output[0]["source_unit"] == "lbs"
    assert output[0]["original"] == format(expected.quantize(Decimal("0.01")), "f")
    assert rows[0]["numeric"] == Decimal("165.35")
    assert rows[0]["original"] == "165.35"
    assert original["value"] == "165.35"
    assert original["unit"] == "lbs"


def test_mismatched_or_absent_units_are_not_guessed():
    exam = date(2025, 4, 3)
    bad = [
        _entry(exam, "Weight", 75, "unknown"),
        _entry(exam, "Body Fat Percentage", "0.20", "ratio"),
        _entry(exam, "Skeletal Muscle Mass", "34.40", ""),
        _entry(exam, "Left Arm - Weight", 4.2, "kg"),
        _entry(exam, "Brazo derecho - Masa musculoesquelética", 4.8, "kg"),
    ]
    norm = dashboard._normalize_records(bad)
    assert dashboard._metric_points(norm, "Weight", "kg") == []
    assert dashboard._metric_points(norm, "Skeletal Muscle Mass", "kg") == []
    assert dashboard._metric_points(norm, "Body Fat Percentage", "%") == []


def test_duplicate_same_day_prefers_muscle_fat_section_in_spanish():
    exam = date(2025, 4, 3)
    rows = dashboard._normalize_records([
        _entry(exam, "Weight", "75.00", "kg", "Research Parameters"),
        _entry(exam, "Peso", "74.90", "kg", "Análisis músculo-grasa"),
    ])
    points = dashboard._metric_points(rows, "Weight", "kg")
    assert len(points) == 1
    assert points[0]["numeric"] == Decimal("74.90")


def test_prefix_aliases_do_not_confuse_segmental_with_whole_body():
    assert dashboard._base_metric("Left Leg - Skeletal Muscle Mass") is None
    assert dashboard._base_metric("Brazo izquierdo - Peso") is None
    assert dashboard._base_metric("Tronco - Peso corporal") is None


def test_gradio_startup_compatibility_contracts():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "row_limits=(1, None)" not in app
    assert "python_version: \"3.12\"" in readme.split("---", 2)[1]
    assert "gradio[oauth]>=6.0,<7.0" in (
        root / "requirements.txt"
    ).read_text(encoding="utf-8")
