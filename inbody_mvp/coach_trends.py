"""Private compact InBody trends for the coach: first + 10 most recent exams.

The UI charts are loaded independently of Gemini and of the coach's 30–365
day conversation context. A reviewed audit view is preferred; the confirmed
legacy table is used only when no reviewed audit rows exist. Neither query
sends a report, patient identifier or source file to the browser.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import plotly.graph_objects as go
from sqlalchemy import text

from .coach_data import resolve_private_person_id
from .progress_dashboard import _base_metric, _metric_points, _normalize_records, _slug
from .storage import _database_engine, canonical_person_id, require_database_access

RECENT_EXAMS = 10
MAX_EXAM_DATES = RECENT_EXAMS + 1
MAX_QUERY_ROWS = 3500
COACH_TREND_METRICS = (
    ("Weight", "Peso", "kg"),
    ("Skeletal Muscle Mass", "Masa muscular esquelética", "kg"),
    ("Body Fat Percentage", "Grasa corporal", "%"),
    ("InBody Score", "Puntaje InBody", "puntos"),
)

# Select dates before selecting measurement rows: a LIMIT on measurements
# would otherwise remove the earliest examination in a long patient history.
_REVIEWED_SQL = text("""
WITH dates AS (
  SELECT DISTINCT v.exam_date
  FROM public.hj_audit_reviewed_private v
  JOIN public.hj_person_aliases p ON p.anonymous_id = v.anonymous_id
  WHERE p.normalized_person_id = :person_key
    AND v.exam_date IS NOT NULL
), chosen AS (
  SELECT exam_date FROM (
    SELECT exam_date FROM dates ORDER BY exam_date ASC LIMIT 1
  ) first_exam
  UNION
  SELECT exam_date FROM (
    SELECT exam_date FROM dates ORDER BY exam_date DESC LIMIT 10
  ) latest_exams
)
SELECT v.exam_date AS exam_date, v.section, v.measurement,
       v.value, v.unit, v.was_corrected
FROM public.hj_audit_reviewed_private v
JOIN public.hj_person_aliases p ON p.anonymous_id = v.anonymous_id
JOIN chosen c ON c.exam_date = v.exam_date
WHERE p.normalized_person_id = :person_key
ORDER BY v.exam_date ASC, v.section, v.measurement
LIMIT :row_limit
""")

_CONFIRMED_SQL = text("""
WITH dates AS (
  SELECT DISTINCT CAST(e.exam_timestamp AS date) AS exam_date
  FROM public.hj_exams e
  JOIN public.hj_persons p ON p.person_uuid = e.person_uuid
  JOIN public.hj_measurements m ON m.exam_uuid = e.exam_uuid
  WHERE (regexp_replace(p.id_persona, '[^0-9]', '', 'g') = :person_key
         OR upper(trim(p.id_persona)) = :person_key)
    AND e.exam_timestamp IS NOT NULL
    AND m.confirmation_status = 'confirmed'
), chosen AS (
  SELECT exam_date FROM (
    SELECT exam_date FROM dates ORDER BY exam_date ASC LIMIT 1
  ) first_exam
  UNION
  SELECT exam_date FROM (
    SELECT exam_date FROM dates ORDER BY exam_date DESC LIMIT 10
  ) latest_exams
)
SELECT CAST(e.exam_timestamp AS date) AS exam_date,
       COALESCE(m.categoria, '') AS section,
       m.variable_medida AS measurement,
       m.valor_medida AS value, m.unidad_medida AS unit,
       FALSE AS was_corrected
FROM public.hj_measurements m
JOIN public.hj_exams e ON e.exam_uuid = m.exam_uuid
JOIN public.hj_persons p ON p.person_uuid = e.person_uuid
JOIN chosen c ON c.exam_date = CAST(e.exam_timestamp AS date)
WHERE (regexp_replace(p.id_persona, '[^0-9]', '', 'g') = :person_key
       OR upper(trim(p.id_persona)) = :person_key)
  AND m.confirmation_status = 'confirmed'
ORDER BY CAST(e.exam_timestamp AS date) ASC, m.row_number
LIMIT :row_limit
""")


def first_and_last_ten_exam_dates(records: list[dict]) -> list[date]:
    """Distinct exam dates, chronologically ascending, with no repeated first.

    The approved audit view exposes only exam_date (not its time). Multiple
    exams on the same date cannot be disambiguated and share one x-axis point.
    """
    dates = set()
    for row in records:
        raw = row.get("exam_date")
        if isinstance(raw, datetime):
            dates.add(raw.date())
        elif isinstance(raw, date):
            dates.add(raw)
        else:
            try:
                dates.add(date.fromisoformat(str(raw or "")[:10]))
            except ValueError:
                continue
    ordered = sorted(dates)
    return sorted(set(ordered[:1] + ordered[-RECENT_EXAMS:]))


def load_private_coach_trend_rows(*, profile=None, request=None) -> tuple[list[dict], str]:
    """Authorized, parameterized history read with earliest + latest dates.

    A selected date is read as a unit to avoid truncating selected exams.
    The 3500-row guard is deliberately conservative and surfaced in the UI.
    """
    require_database_access(oauth_profile=profile, request=request)
    key = canonical_person_id(
        resolve_private_person_id(profile=profile, request=request)
    )
    engine = _database_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                _REVIEWED_SQL,
                {"person_key": key, "row_limit": MAX_QUERY_ROWS + 1},
            ).mappings().all()
            source = "auditorías InBody revisadas"
            if not rows:
                rows = conn.execute(
                    _CONFIRMED_SQL,
                    {"person_key": key, "row_limit": MAX_QUERY_ROWS + 1},
                ).mappings().all()
                source = "mediciones InBody confirmadas"
    finally:
        engine.dispose()
    if len(rows) > MAX_QUERY_ROWS:
        raise ValueError(
            "El historial seleccionado supera el límite de visualización. "
            "No se mostrarán tendencias incompletas."
        )
    return [
        {
            "exam_date": (
                r["exam_date"].isoformat()
                if isinstance(r["exam_date"], (date, datetime))
                else str(r["exam_date"] or "")
            ),
            "section": str(r["section"] or ""),
            "measurement": str(r["measurement"] or ""),
            "value": str(r["value"]) if r["value"] is not None else None,
            "unit": str(r["unit"] or ""),
            "was_corrected": bool(r["was_corrected"]),
        }
        for r in rows
    ], source


def _score_points(rows: list[dict]) -> list[dict]:
    allowed = {"inbody score", "puntaje inbody", "puntuacion inbody"}
    allowed_units = {"", "point", "points", "pt", "pts", "punto", "puntos"}
    by_date = {}
    for row in sorted(rows, key=lambda r: (
        r["date"], r["section"], r["measurement"]
    )):
        name = _slug(row["measurement"])
        if (name in allowed or (
            name in {"score", "puntaje"}
            and _slug(row["section"]) == "inbody score"
        )) and _slug(row["unit"]) in allowed_units:
            by_date[row["date"]] = row
    return [by_date[d] for d in sorted(by_date)]


def _compact_figure(
    label: str, unit: str, points: list[dict],
    selected_dates: list[date] | None = None,
) -> go.Figure:
    """Expose the exact chosen examination dates, especially the first.

    The x-axis is an ordinal exam axis, like the printed InBody history:
    points have equal spacing even when the first test is years older.
    All chosen exam positions stay visible, including missing values.
    Never interpolate a missing measurement or silently drop its date.
    """
    selected_dates = sorted(set(selected_dates or []))
    fig = go.Figure()
    measured = {row["date"]: row for row in points}
    available = [measured[d] for d in selected_dates if d in measured]
    if selected_dates:
        positions = list(range(len(selected_dates)))
        values = [
            float(measured[d]["numeric"]) if d in measured else None
            for d in selected_dates
        ]
        originals = [
            measured[d]["original"] if d in measured else "Sin medición"
            for d in selected_dates
        ]
        fig.add_trace(go.Scatter(
            x=positions,
            y=values,
            mode="lines+markers",
            connectgaps=False,
            line={"width": 2, "color": "#37766b"},
            marker={
                "size": [9] + [5] * (len(positions) - 1),
                "color": ["#b67b25"] + ["#294c44"] * (len(positions) - 1),
                "symbol": ["diamond"] + ["circle"] * (len(positions) - 1),
            },
            text=originals,
            customdata=[d.strftime("%d/%m/%Y") for d in selected_dates],
            hovertemplate=(
                "%{customdata}<br>%{text} " + unit + "<extra></extra>"
            ),
            showlegend=False,
        ))
        # Gradio/Plotly's automatic date ticks previously hid the first
        # date label. Place the first and last exams explicitly on the axis.
        first = selected_dates[0]
        last = selected_dates[-1]
        tickvals = [0] if len(positions) == 1 else [0, positions[-1]]
        ticktext = (
            [f"1.ª {first:%d/%m/%y}"] if len(positions) == 1
            else [f"1.ª {first:%d/%m/%y}", f"Últ. {last:%d/%m/%y}"]
        )
        fig.update_xaxes(
            type="linear", tickmode="array", tickvals=tickvals,
            ticktext=ticktext, tickfont={"size": 9},
            tickangle=0, range=[-0.4, positions[-1] + 0.4],
            showgrid=False, showline=False,
            automargin=True, fixedrange=True, title=None,
        )
        if first not in measured:
            fig.add_annotation(
                text="1.ª prueba: sin esta medida",
                x=0.01, y=0.95, xref="paper", yref="paper",
                xanchor="left", showarrow=False,
                font={"size": 9, "color": "#8c6432"},
            )
    if available:
        latest = available[-1]
        title = f"<b>{label}</b> · {latest['original']} {unit}"
    else:
        title = f"<b>{label}</b> · sin datos"
        fig.add_annotation(
            text="Sin mediciones suficientes", x=0.5, y=0.5,
            xref="paper", yref="paper", showarrow=False,
            font={"size": 11, "color": "#75817d"},
        )
    fig.update_layout(
        title={"text": title, "font": {"size": 12}, "x": 0.02, "y": 0.97},
        height=150,
        margin={"l": 34, "r": 14, "t": 33, "b": 41},
        showlegend=False, hovermode="closest",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    if not selected_dates:
        fig.update_xaxes(showgrid=False, showline=False, title=None)
    fig.update_yaxes(
        tickfont={"size": 9}, showgrid=True,
        gridcolor="rgba(110,130,120,.11)", zeroline=False, title=None,
    )
    return fig


def render_coach_trend_figures(records: list[dict]):
    """Four compact figures, ordered first-date + ten latest-date points."""
    selected_dates = first_and_last_ten_exam_dates(records)
    allowed_dates = set(selected_dates)
    normalized = [
        r for r in _normalize_records(records)
        if r["date"] in allowed_dates
    ]
    figures = []
    for code, label, unit in COACH_TREND_METRICS:
        if code == "InBody Score":
            points = _score_points(normalized)
        else:
            points = _metric_points(normalized, code, unit)
        figures.append(_compact_figure(label, unit, points, selected_dates))
    return figures, len(selected_dates)


def empty_coach_trend_figures():
    return [
        _compact_figure(label, unit, [])
        for _, label, unit in COACH_TREND_METRICS
    ]
