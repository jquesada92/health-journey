"""Private InBody historical trends and latest-value comparisons in Plotly.

Inputs come ONLY from an OAuth-authorized pseudonymous Neon view. Never
accept raw PDF history plots as datapoints or expose a real person ID.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Canonical English names in the Gemini extraction contract.
# Each metric is compared only against the same metric and unit.
METRICS = (
    ("Weight", "Peso", "kg"),
    ("Skeletal Muscle Mass", "Masa muscular esquelética", "kg"),
    ("Body Fat Mass", "Masa grasa corporal", "kg"),
    ("Body Fat Percentage", "Porcentaje de grasa", "%"),
    ("ECW Ratio", "Relación ECW", ""),
)
ALIASES = {
    "weight": "Weight",
    "skeletal muscle mass": "Skeletal Muscle Mass",
    "smm": "Skeletal Muscle Mass",
    "smm skeletal muscle mass": "Skeletal Muscle Mass",
    "body fat mass": "Body Fat Mass",
    "bfm": "Body Fat Mass",
    "bfm body fat mass": "Body Fat Mass",
    "body fat percentage": "Body Fat Percentage",
    "percent body fat": "Body Fat Percentage",
    "pbf": "Body Fat Percentage",
    "pbf percent body fat": "Body Fat Percentage",
    "ecw ratio": "ECW Ratio",
    "ecw tbw": "ECW Ratio",
    "extracellular water ratio": "ECW Ratio",
}
SECTIONS = (
    "Todas las secciones",
    "Body Composition Analysis",
    "Muscle-Fat Analysis",
    "Obesity Analysis",
    "Segmental Lean Analysis",
    "Segmental Fat Analysis",
    "Segmental ECW Analysis",
    "ECW Ratio-Phase Angle",
    "Research Parameters",
    "Weight Control",
    "InBody Score",
    "Impedance",
)
PRIORITY_SECTIONS = {
    "Weight": ("Muscle-Fat Analysis", "Body Composition Analysis"),
    "Skeletal Muscle Mass": ("Muscle-Fat Analysis",),
    "Body Fat Mass": ("Muscle-Fat Analysis", "Body Composition Analysis"),
    "Body Fat Percentage": ("Obesity Analysis",),
    "ECW Ratio": ("ECW Ratio-Phase Angle", "Research Parameters"),
}
DETAIL_COLUMNS = [
    "Section", "Measurement", "Current", "Unit", "Previous",
    "Change vs previous", "Last measured", "Corrected",
]
HISTORY_COLUMNS = [
    "Fecha", "Medición", "Valor", "Unidad", "Cambio vs anterior",
]


def _parse_date(value, name: str):
    if value is None or str(value).strip() == "":
        return None
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} debe ser una fecha válida (AAAA-MM-DD).") from exc


def _number(value):
    """Chart-only conversion; the original decimal string remains unchanged."""
    try:
        parsed = Decimal(str(value).strip().replace(",", "."))
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _slug(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def _base_metric(name):
    raw = str(name or "").strip()
    # Body segment results must not pollute whole-body KPI series.
    if re.match(r"^(right|left) (arm|leg) - |^trunk - ", raw, flags=re.I):
        return None
    return ALIASES.get(_slug(raw))


def _relative(current, previous):
    if previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * Decimal(100)


def _change_label(current, previous):
    change = _relative(current, previous)
    if change is None:
        return "—"
    arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
    return f"{arrow} {change:+.1f}%"


def _empty_figure(message):
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    fig.update_layout(height=245, margin=dict(l=25, r=25, t=35, b=30))
    return fig


def _indicator(label, unit, pair):
    if not pair:
        return _empty_figure(f"{label}: sin mediciones")
    current, previous, original = pair
    places = min(len(original.split(".", 1)[1]) if "." in original else 0, 5)
    display = {"valueformat": f".{places}f"}
    if unit:
        display["suffix"] = " " + unit
    settings = dict(
        mode="number",
        value=float(current),
        number=display,
        title={"text": label},
    )
    if previous is not None and previous != 0:
        settings["mode"] = "number+delta"
        # Plotly renders up/down arrows; neutral color avoids equating a
        # decrease in weight or body fat with a bad health outcome.
        settings["delta"] = {
            "reference": float(previous),
            "relative": True,
            "valueformat": ".1%",
            "increasing": {"color": "#7c8796"},
            "decreasing": {"color": "#7c8796"},
        }
    fig = go.Figure(go.Indicator(**settings))
    if previous is None:
        fig.add_annotation(text="Sin medición anterior", x=0.5, y=0.06,
                           xref="paper", yref="paper", showarrow=False,
                           font={"size": 11})
    elif previous == 0:
        fig.add_annotation(text="Referencia anterior = 0", x=0.5, y=0.06,
                           xref="paper", yref="paper", showarrow=False,
                           font={"size": 11})
    fig.update_layout(height=168, margin=dict(l=10, r=10, t=20, b=12),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def _normalize_records(records):
    rows = []
    for record in records:
        numeric = _number(record.get("value"))
        try:
            observed = _parse_date(record.get("exam_date"), "Fecha del examen")
        except ValueError:
            continue
        if numeric is None or observed is None:
            continue
        # Never retain person_id, filename, source hash, age or raw response.
        rows.append({
            "date": observed,
            "section": str(record.get("section") or ""),
            "measurement": str(record.get("measurement") or ""),
            "original": str(record["value"]),
            "numeric": numeric,
            "unit": str(record.get("unit") or ""),
            "corrected": bool(record.get("was_corrected")),
        })
    return rows


def _metric_points(rows, metric, expected_unit):
    matches = [r for r in rows
               if _base_metric(r["measurement"]) == metric
               and r["unit"] == expected_unit]
    priority = PRIORITY_SECTIONS.get(metric, ())
    # Prefer the canonical section for any repeated metric on one date.
    matches.sort(key=lambda r: (
        r["date"],
        len(priority) - priority.index(r["section"])
        if r["section"] in priority else 0,
        r["section"], r["measurement"],
    ))
    by_day = {}
    for r in matches:
        by_day[r["date"]] = r
    return [by_day[key] for key in sorted(by_day)]


def _series_figure(points_by_metric):
    available = [(name, unit, points_by_metric[name])
                 for name, _, unit in METRICS if points_by_metric[name]]
    if not available:
        return _empty_figure("No hay mediciones históricas en el rango seleccionado.")
    fig = make_subplots(
        rows=len(available), cols=1, shared_xaxes=True,
        vertical_spacing=min(0.12, 0.28 / len(available)),
        subplot_titles=[name for name, _, _ in available],
    )
    for index, (name, unit, points) in enumerate(available, 1):
        fig.add_trace(go.Scatter(
            x=[p["date"] for p in points],
            y=[float(p["numeric"]) for p in points],
            mode="lines+markers+text",
            text=[p["original"] for p in points],
            textposition="top center",
            name=name,
            hovertemplate=f"%{{x|%Y-%m-%d}} · %{{text}} {unit}<extra>{name}</extra>",
            showlegend=False,
        ), row=index, col=1)
        fig.update_yaxes(title_text=unit or "ratio", row=index, col=1)
    fig.update_layout(
        height=max(360, len(available) * 175),
        margin=dict(l=70, r=25, t=65, b=45),
        hovermode="closest",
    )
    fig.update_xaxes(title_text="Fecha del examen", row=len(available), col=1)
    return fig


def _score_figure(rows):
    """Plot the InBody Score of each recorded exam as a date-filtered line.

    Score comes from reviewed Neon measurements, NOT the historical image
    embedded in a PDF. Accept the English standardized term plus legacy
    Spanish labels and common point units, never other score-like measures.
    """
    valid_names = {"inbody score", "puntaje inbody", "puntuacion inbody"}
    valid_units = {"", "points", "point", "puntos", "pts", "pt"}
    matches = [
        row for row in rows
        if (
            _slug(row["measurement"]) in valid_names
            or (
                _slug(row["measurement"]) in {"score", "puntaje"}
                and _slug(row["section"]) == "inbody score"
            )
        )
        and row["unit"].strip().lower() in valid_units
    ]
    by_date = {}
    for row in sorted(matches, key=lambda x: (
        x["date"], x["section"], x["measurement"]
    )):
        by_date[row["date"]] = row
    if not by_date:
        return _empty_figure(
            "Todavía no hay puntajes InBody revisados en el rango seleccionado."
        )
    points = [by_date[key] for key in sorted(by_date)]
    fig = go.Figure(go.Scatter(
        x=[p["date"] for p in points],
        y=[float(p["numeric"]) for p in points],
        mode="lines+markers+text",
        text=[p["original"] for p in points],
        textposition="top center",
        name="InBody Score",
        hovertemplate="%{x|%Y-%m-%d} · %{text} puntos<extra>InBody Score</extra>",
    ))
    fig.update_layout(
        title="Evolución del puntaje InBody",
        xaxis_title="Fecha del examen",
        yaxis_title="Puntos",
        height=350,
        margin=dict(l=55, r=25, t=65, b=55),
        hovermode="closest",
    )
    return fig


def _latest_group(rows):
    # One current measurement per section, label and unit.
    # Multiple same-date reports are ambiguous in the date-only view;
    # prefer no invented ordering or averages.
    groups = {}
    for row in rows:
        groups.setdefault(
            (row["section"], row["measurement"], row["unit"]), []
        ).append(row)
    latest = []
    for (section, measurement, unit), group in groups.items():
        by_day = {}
        for row in sorted(group, key=lambda x: x["date"]):
            by_day.setdefault(row["date"], row)
        sorted_rows = [by_day[d] for d in sorted(by_day)]
        curr = sorted_rows[-1]
        prev = sorted_rows[-2] if len(sorted_rows) >= 2 else None
        latest.append({
            "Section": section,
            "Measurement": measurement,
            "Current": curr["original"],
            "Unit": unit,
            "Previous": prev["original"] if prev else "—",
            "Change vs previous": _change_label(
                curr["numeric"], prev["numeric"] if prev else None),
            "Last measured": curr["date"].isoformat(),
            "Corrected": curr["corrected"],
        })
    return pd.DataFrame(sorted(latest, key=lambda x: (
        x["Section"], x["Measurement"], x["Unit"])), columns=DETAIL_COLUMNS)


def _detail_plot(detail_frame, section):
    if section == SECTIONS[0]:
        return _empty_figure("Selecciona una sección para comparar sus medidas.")
    selected = detail_frame[detail_frame["Section"] == section]
    if selected.empty:
        return _empty_figure("No hay mediciones de esta sección.")
    # Measurements with different units must never share an axis.
    units = sorted(selected["Unit"].unique().tolist())
    fig = make_subplots(
        rows=len(units), cols=1,
        subplot_titles=[f"Unidad: {unit or 'sin unidad'}" for unit in units],
        vertical_spacing=min(0.18, 0.30 / max(len(units), 1)),
    )
    for index, unit in enumerate(units, 1):
        group = selected[selected["Unit"] == unit].copy()
        numeric_current = [float(_number(v)) for v in group["Current"]]
        fig.add_trace(go.Bar(
            y=group["Measurement"], x=numeric_current,
            orientation="h", name="Actual", legendgroup="current",
            showlegend=index == 1,
            text=group["Current"], textposition="outside",
        ), row=index, col=1)
        prev = group[group["Previous"] != "—"]
        if not prev.empty:
            fig.add_trace(go.Bar(
                y=prev["Measurement"],
                x=[float(_number(v)) for v in prev["Previous"]],
                orientation="h", name="Anterior", legendgroup="previous",
                showlegend=index == 1,
            ), row=index, col=1)
        fig.update_xaxes(title_text=unit, row=index, col=1)
    fig.update_layout(
        barmode="group",
        height=max(300, 135 * len(selected) + 100 * len(units)),
        margin=dict(l=175, r=55, t=65, b=35),
    )
    return fig


def render_progress(records, from_date=None, to_date=None,
                    selected_section="Todas las secciones"):
    """Return Plotly KPI + trend charts and long-format tables, without PII.

    The previous value is the preceding DISTINCT DATE within the selected
    period and the same metric/unit. No exam selector is required.
    """
    start = _parse_date(from_date, "Desde")
    end = _parse_date(to_date, "Hasta")
    if start and end and start > end:
        raise ValueError("La fecha inicial no puede ser posterior a la final.")
    rows = [r for r in _normalize_records(records)
            if (start is None or r["date"] >= start)
            and (end is None or r["date"] <= end)]
    values = {metric: _metric_points(rows, metric, unit)
              for metric, _, unit in METRICS}
    indicators = []
    history = []
    for metric, label, unit in METRICS:
        series = values[metric]
        current = series[-1] if series else None
        previous = series[-2] if len(series) > 1 else None
        pair = (current["numeric"], previous["numeric"] if previous else None,
                current["original"]) if current else None
        indicators.append(_indicator(label, unit, pair))
        for index, item in enumerate(series):
            prior = series[index - 1] if index else None
            history.append({
                "Fecha": item["date"].isoformat(),
                "Medición": metric,
                "Valor": item["original"],
                "Unidad": unit,
                "Cambio vs anterior": _change_label(
                    item["numeric"], prior["numeric"] if prior else None),
            })
    summary = pd.DataFrame(history, columns=HISTORY_COLUMNS)
    detail = _latest_group(rows)
    if selected_section != SECTIONS[0]:
        selected = detail[detail["Section"] == selected_section].copy()
    else:
        selected = detail
    trend = _series_figure(values)
    detail_chart = _detail_plot(detail, selected_section)
    date_count = len({r["date"] for r in rows})
    status = (
        f"{date_count} fecha(s) de examen y {len(rows)} mediciones revisadas "
        "dentro del rango. Las flechas muestran cambios respecto a la "
        "fecha anterior disponible dentro del filtro, no una valoración médica."
        if rows else "Sin mediciones revisadas para el rango seleccionado."
    )
    score_trend = _score_figure(rows)
    return (status, *indicators, trend, summary, selected, detail_chart, score_trend)
