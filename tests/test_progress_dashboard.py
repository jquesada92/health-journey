"""Synthetic regression tests for private Plotly historical InBody progress."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import pandas as pd
import plotly.graph_objects as go

from inbody_mvp.progress_dashboard import (
    METRICS, SECTIONS, _change_label, render_progress,
)

ROOT = Path(__file__).resolve().parents[1]


def report_rows(day, weight, smm, fat, pbf, ecw, lean):
    measures = [
        ("Muscle-Fat Analysis", "Weight", weight, "kg"),
        ("Muscle-Fat Analysis", "SMM Skeletal Muscle Mass", smm, "kg"),
        ("Muscle-Fat Analysis", "Body Fat Mass", fat, "kg"),
        ("Obesity Analysis", "PBF Percent Body Fat", pbf, "%"),
        ("Research Parameters", "ECW Ratio", ecw, ""),
        ("Segmental Lean Analysis", "Right Arm - Lean Mass", lean, "kg"),
    ]
    return [{
        "anonymous_id": "11111111-2222-4333-8888-999999999999",
        "exam_date": day,
        "section": section,
        "measurement": name,
        "value": value,
        "unit": unit,
        "was_corrected": False,
        "person_id": "88571257",  # malicious extra field is NEVER exposed
        "filename": "inbody_private.jpg",
    } for section, name, value, unit in measures]


@pytest.fixture
def records():
    return (
        report_rows("2026-08-07", "73.6", "33.1", "15.6", "21.1", "0.369", "3.20")
        + report_rows("2026-08-29", "72.0", "32.9", "14.5", "20.1", "0.368", "3.35")
        + report_rows("2026-09-27", "71.6", "31.9", "15.4", "21.5", "0.370", "3.50")
        + report_rows("2026-10-04", "72.4", "32.9", "14.6", "20.2", "0.370", "3.69")
    )


def test_indicators_use_previous_measurement_and_relative_difference(records):
    result = render_progress(records)
    assert len(result) == 10
    assert len(METRICS) == 5
    weight_fig = result[1]
    assert isinstance(weight_fig, go.Figure)
    trace = weight_fig.data[0]
    assert trace.type == "indicator"
    assert trace.value == pytest.approx(72.4)
    assert trace.delta.reference == pytest.approx(71.6)
    assert trace.delta.relative is True
    assert trace.delta.valueformat == ".1%"
    assert trace.delta.decreasing.color == "#7c8796"
    assert result[2].data[0].delta.reference == pytest.approx(31.9)
    assert result[4].data[0].delta.reference == pytest.approx(21.5)
    # ECW is unchanged; still shows neutral arrow rather than good/bad.
    assert result[5].data[0].delta.reference == pytest.approx(.370)
    assert "4 fecha(s)" in result[0]
    history = result[7]
    weight = history[history["Medición"] == "Weight"].sort_values("Fecha")
    assert weight.iloc[-1]["Cambio vs anterior"] == "↑ +1.1%"
    assert weight.iloc[-2]["Cambio vs anterior"] == "↓ -0.6%"


def test_filter_date_range_updates_current_previous_and_keeps_exact_decimals(records):
    result = render_progress(records, "2026-08-01", "2026-09-30")
    assert result[1].data[0].value == pytest.approx(71.6)
    assert result[1].data[0].delta.reference == pytest.approx(72.0)
    assert "3 fecha(s)" in result[0]
    detail = result[8]
    lean = detail[detail["Measurement"] == "Right Arm - Lean Mass"].iloc[0]
    assert lean["Current"] == "3.50"
    assert lean["Previous"] == "3.35"
    assert "88571257" not in detail.to_string()
    assert "inbody_private" not in detail.to_string()
    assert "person_id" not in detail.columns
    assert "age" not in detail.columns
    assert "filename" not in detail.columns


def test_missing_previous_and_zero_reference_do_not_crash():
    row = report_rows("2026-08-29", "0.00", "30.0", "14.5", "20.1", "0.370", "3.50")
    only = render_progress(row)
    assert only[1].data[0].mode == "number"
    assert "Sin medición anterior" in str(only[1].layout.annotations)
    next_row = report_rows("2026-09-01", "72.4", "30.2", "14.2", "20.0", "0.370", "3.50")
    both = render_progress(row + next_row)
    assert both[1].data[0].mode == "number"
    assert both[7].loc[both[7]["Medición"] == "Weight"].iloc[-1]["Cambio vs anterior"] == "—"


def test_invalid_dates_and_empty_period(records):
    with pytest.raises(ValueError, match="fecha inicial"):
        render_progress(records, "2026-10-10", "2026-10-01")
    with pytest.raises(ValueError, match="fecha válida"):
        render_progress(records, "banana")
    empty = render_progress(records, "2025-01-01", "2025-12-31")
    assert "Sin mediciones" in empty[0]
    assert empty[7].empty and empty[8].empty


def test_segmental_values_not_used_as_whole_body_metrics(records):
    truncated = [x for x in records if x["measurement"].startswith("Right Arm - ")]
    result = render_progress(truncated, selected_section="Segmental Lean Analysis")
    assert result[1].data == ()
    detail = result[8]
    assert detail.iloc[-1]["Current"] == "3.69"
    assert "3.69" in str(result[9].data[0].text)


def test_history_is_date_separated_and_never_uses_pdf_trend_values(records):
    selected = render_progress(records)
    figure = selected[6]
    assert figure.data[0].name == "Weight"
    assert list(figure.data[0].y) == [73.6, 72.0, 71.6, 72.4]
    assert "Body Composition History" not in selected[8].to_string()
    assert _change_label(Decimal("8.20"), Decimal("8.00")).startswith("↑")


def test_gradio_contract_date_filters_plotly_and_no_exam_selector():
    app = (ROOT / "app.py").read_text()
    assert 'with gr.Tab("Dashboard")' in app
    assert app.count('with gr.Tab("Dashboard")') == 1
    assert 'with gr.Tab("Dashboard público")' not in app
    assert 'with gr.Tab("Progress Dashboard")' not in app
    assert 'with gr.Tab("Dashboard (siguiente fase)")' not in app
    assert 'with gr.Accordion("Mi progreso histórico (acceso privado)"' in app
    assert 'with gr.Accordion("Mediciones publicadas (solo datos aprobados)"' in app
    assert "progress_start = gr.DateTime(" in app
    assert "progress_end = gr.DateTime(" in app
    assert "fn=show_progress" in app or "progress_refresh.click(" in app
    assert 'progress_kpis = [' in app
    assert 'progress_section = gr.Dropdown(' in app
    assert "progress_refresh.click(" in app
    assert "load_reviewed_audit_history(" in app
    assert "profile: gr.OAuthProfile | None = None" in app
    section = app[app.index('with gr.Tab("Dashboard")'):app.index('with gr.Tab("Historial en Neon")')]
    assert "exam_selector" not in section
    assert "alias privado test" in section
    assert "Exam selector" not in section
    assert '"type=password"' not in section  # uses correctly typed Gradio keyword
    assert 'type="password"' in section
    assert len(METRICS) == 5
    assert SECTIONS[0] == "Todas las secciones"
