"""Health Journey - first-phase Dash upload and extraction sandbox.

Run `python dash_app.py` after installing requirements. Does not change
app.py (the existing Gradio/ZeroGPU entrypoint), does not persist health data.
"""
from __future__ import annotations

import base64
import csv
import io
import math
import os
from datetime import datetime

import dash_ag_grid as dag
from dash import Dash, Input, Output, State, callback, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import Flask
from pydantic import ValidationError

from inbody_mvp.extractor import DocumentError, ExtractionResult, MAX_UPLOAD_BYTES, extract_document

server = Flask(__name__)
# Dash sends base64 in a JSON request (~1.33x binary size), with some overhead.
server.config["MAX_CONTENT_LENGTH"] = 23 * 1024 * 1024
app = Dash(__name__, server=server, title="Health Journey | InBody Hub", suppress_callback_exceptions=True)

STYLE = {
    "fontFamily": "system-ui, -apple-system, Segoe UI, sans-serif",
    "maxWidth": "1200px", "margin": "30px auto", "padding": "0 20px", "color": "#17212f",
}
CARD = {"background": "#f3f6fb", "padding": "14px", "borderRadius": "10px", "marginTop": "12px"}
FIELDS = [
    {"field": "original_label", "headerName": "Etiqueta original", "editable": False, "flex": 2, "minWidth": 170},
    {"field": "variable_medida", "headerName": "Medición normalizada", "editable": True, "flex": 2, "minWidth": 170},
    {"field": "segmento", "headerName": "Segmento", "editable": True, "minWidth": 130},
    {"field": "frecuencia_khz", "headerName": "kHz", "editable": True, "minWidth": 85},
    {"field": "unidad_medida", "headerName": "Unidad", "editable": True, "minWidth": 90},
    {"field": "valor_medida", "headerName": "Valor", "editable": True, "minWidth": 95},
    {"field": "pagina", "headerName": "Página", "editable": False, "minWidth": 95},
    {"field": "fuente", "headerName": "Origen", "editable": False, "minWidth": 110},
]

app.layout = html.Main([
    html.H1("Health Journey · InBody Hub"),
    html.P("Fase 1: subir PDF, JPG, JPEG o PNG, revisar mediciones y exportar un borrador CSV."),
    html.P("QA local: no se guarda ningún informe en una base de datos. Usa archivos anonimizados."),
    dcc.Upload(
        id="inbody-upload",
        children=html.Div([html.Strong("Arrastra tu reporte aquí"), html.Span(" o haz clic para seleccionarlo")]),
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png",
        multiple=False,
        style={
            "border": "2px dashed #7189ab", "padding": "34px", "textAlign": "center",
            "borderRadius": "12px", "cursor": "pointer", "background": "#f8fbff",
        },
    ),
    html.Div(id="upload-status", role="status", style=CARD),
    dcc.Loading(html.Div(id="result-panel")),
    dcc.Store(id="extraction-state", storage_type="memory"),
    dcc.Download(id="download-draft"),
], style=STYLE)


def _rows(data: dict) -> list[dict]:
    return [{k: v for k, v in m.items()} for m in data.get("medidas", [])]


def make_measurement_key(row: dict) -> str:
    """Keep segment/frequency distinct in the seven-column interchange format."""
    base = str(row.get("variable_medida") or "sin_clasificar").strip()
    if base == "sin_clasificar":
        import re
        original = str(row.get("original_label") or "medida_desconocida")
        suffix = re.sub(r"[^a-zA-Z0-9]+", "_", original).strip("_").lower()
        base += f"__{suffix}"
    segment = str(row.get("segmento") or "").strip()
    frequency = row.get("frecuencia_khz")
    if segment:
        base += f"__{segment}"
    if frequency is not None and str(frequency).strip() != "":
        base += f"__{float(frequency):g}khz"
    return base


def draft_csv(rows: list[dict], person_id: str | None, model: str | None,
              timestamp: str | None, age: int | None) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id_persona", "modelo_inbody", "timestamp", "variable_medida",
                     "unidad_medida", "valor_medida", "edad"])
    for row in rows:
        try:
            value = float(str(row.get("valor_medida", "")).replace(",", "."))
            if not math.isfinite(value):
                value = ""
        except (ValueError, TypeError):
            value = ""
        writer.writerow([person_id or "", model or "", timestamp or "",
                         make_measurement_key(row), row.get("unidad_medida") or "", value,
                         age if age is not None else ""])
    return output.getvalue()


@callback(
    Output("extraction-state", "data"), Output("upload-status", "children"),
    Input("inbody-upload", "contents"), State("inbody-upload", "filename"),
    prevent_initial_call=True,
)
def handle_upload(contents: str | None, filename: str | None):
    if not contents:
        raise PreventUpdate
    try:
        _, payload = contents.split(",", 1)
        # Fail before decoding extremely large uploads.
        if len(payload) > ((MAX_UPLOAD_BYTES + 2) // 3 * 4) + 4:
            raise DocumentError("El archivo supera el máximo permitido de 15 MB.")
        raw = base64.b64decode(payload, validate=True)
        result = extract_document(filename or "", raw)
        return result.model_dump(mode="json"), (
            f"Archivo: {filename} · {len(result.medidas)} candidatos · "
            f"{len(result.texto_por_pagina)} página(s) · "
            "revisión humana pendiente."
        )
    except (ValueError, DocumentError, UnicodeError) as exc:
        return None, f"No se pudo procesar el archivo: {exc}"
    except Exception as exc:
        # Avoid surfacing health/document text or a full stack trace to the browser.
        return None, f"Error al procesar el archivo ({type(exc).__name__})."


@callback(Output("result-panel", "children"), Input("extraction-state", "data"))
def render_results(data: dict | None):
    if not data:
        return html.Div("Carga un PDF o imagen para empezar.", style=CARD)
    try:
        validated = ExtractionResult.model_validate(data)
    except ValidationError:
        return html.Div("Los resultados no tienen un formato válido.", style=CARD)
    text_preview = "\n\n----- Página siguiente -----\n\n".join(validated.texto_por_pagina)
    return html.Div([
        html.H2("Metadatos del examen (editables)"),
        html.Div([
            html.Label("Cédula o ID de la persona"),
            dcc.Input(id="person-field", value=validated.id_persona or "", type="text", style={"width":"100%"}),
            html.Label("Modelo o identificador InBody"),
            dcc.Input(id="model-field", value=validated.modelo_inbody or "", type="text", style={"width":"100%"}),
            html.Label("Timestamp del examen (sin zona si no aparece en documento)"),
            dcc.Input(id="timestamp-field", value=validated.timestamp or "", type="text", placeholder="AAAA-MM-DDTHH:MM:SS", style={"width":"100%"}),
            html.Label("Edad en fecha del examen"),
            dcc.Input(id="age-field", value=validated.edad, type="number", min=0, max=120, step=1, style={"width":"100%"}),
            html.Small(f"Origen edad: {validated.origen_edad or 'desconocido'}"),
        ], style={**CARD, "display":"grid", "gap":"7px"}),
        html.H2("Mediciones candidatas — revisar todas las filas"),
        html.P("Los valores y su clasificación son candidatos, no resultados confirmados. Doble clic para editar."),
        dag.AgGrid(
            id="measure-grid", rowData=_rows(data), columnDefs=FIELDS,
            defaultColDef={"resizable": True, "sortable": True, "filter": True},
            dashGridOptions={"pagination": True, "paginationPageSize": 15, "singleClickEdit": True},
            style={"height": "370px", "width": "100%"},
        ),
        html.Button("Exportar borrador CSV (sin guardar)", id="export-draft", n_clicks=0,
                    style={"marginTop": "12px", "padding": "10px 18px", "cursor":"pointer"}),
        html.H3("Advertencias de extracción"),
        html.Ul([html.Li(w) for w in validated.advertencias] or [html.Li("Sin advertencias adicionales.")]),
        html.Details([html.Summary("Mostrar texto completo extraído"),
                      dcc.Textarea(value=text_preview, readOnly=True, style={"width":"100%", "height":"260px"})]),
        html.P("Una medición nueva puede quedar 'sin_clasificar'. No se elimina: corrígela en la tabla."),
    ], style=CARD)


@callback(
    Output("download-draft", "data"), Input("export-draft", "n_clicks"),
    State("measure-grid", "rowData"), State("person-field", "value"),
    State("model-field", "value"), State("timestamp-field", "value"),
    State("age-field", "value"), prevent_initial_call=True,
)
def export_draft(n_clicks, rows, person, model, timestamp, age):
    if not n_clicks or not rows:
        raise PreventUpdate
    try:
        if age is not None and age != "":
            age = int(age)
            if not 0 <= age <= 120:
                raise ValueError("Edad fuera de rango")
        else:
            age = None
        if timestamp:
            datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        # Invalid input must not be silently exported as a confirmed measurement.
        return no_update
    content = draft_csv(rows, person, model, timestamp, age)
    return dcc.send_string(content, "inbody_borrador.csv")


if __name__ == "__main__":
    # Public hosting requires authentication and deployment hardening; local only for now.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8050")), debug=False)
