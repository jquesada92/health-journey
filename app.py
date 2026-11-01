"""Health Journey: Gradio + Pydantic for InBody upload, review and CSV drafts.

Runs inside the existing Gradio/ZeroGPU Space. No database or user authentication:
use only synthetic or anonymized InBody reports during QA.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv(override=False)  # Local-only .env; do not commit credentials.

from inbody_mvp.extractor import DocumentError, MAX_UPLOAD_BYTES
from inbody_mvp.public_dashboard import (
    PUBLIC_METRICS, public_dashboard_enabled,
    load_public_monthly_summary, load_public_person_series,
)
from inbody_mvp.oauth_ui import standalone_oauth_urls
from inbody_mvp.demo_storage import (
    anonymous_demo_enabled, anonymous_demo_requested, save_demo_exam,
)
from inbody_mvp.storage import (
    database_enabled, require_report_access, require_database_access, load_measurement_history,
    prepare_confirmed_exam, save_confirmed_exam, source_exam_timestamp,
)

README_PATH = Path(__file__).resolve().with_name("README.md")


def read_readme() -> str:
    if not README_PATH.is_file():
        return "# Health Journey\n\nREADME.md no está disponible."
    text = README_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "".join(lines[index + 1:]).lstrip()
    return text


def snapshot_upload(file_path):
    """Store upload bytes in this Gradio session before temp-file cleanup."""
    if not file_path:
        return None
    path = Path(file_path)
    try:
        if not path.is_file() or path.stat().st_size > MAX_UPLOAD_BYTES:
            raise DocumentError("Archivo inexistente o mayor de 15 MB.")
        return {"filename": path.name, "data": path.read_bytes()}
    except OSError as exc:
        raise gr.Error("No se pudo recibir el archivo. Vuelve a cargarlo.") from exc


def report_from_snapshot(upload_state):
    """Read only the in-session snapshot; never rely on /tmp/gradio later."""
    if not upload_state or not isinstance(upload_state, dict):
        raise DocumentError("Carga nuevamente el reporte para continuar.")
    name, data = upload_state.get("filename"), upload_state.get("data")
    if not name or not isinstance(data, bytes) or len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError("La copia temporal del reporte no está disponible. Vuelve a cargarlo.")
    return name, data


def verify_neon_session(profile: gr.OAuthProfile | None = None) -> str:
    """Only checks HF OAuth and allowlist, never contacts Neon or logs secrets."""
    try:
        require_database_access(profile)
    except PermissionError:
        return (
            "No hay sesión Hugging Face autorizada para Neon. "
            "Inicia sesión desde una pestaña independiente con la cuenta "
            "incluida en HF_ALLOWED_USERS."
        )
    return (
        "Sesión Hugging Face autorizada para operaciones privadas. "
        "La conexión SQL todavía no ha sido comprobada."
    )


OAUTH_URLS = standalone_oauth_urls(os.getenv("SPACE_HOST"))

with gr.Blocks(title="Health Journey", analytics_enabled=False, delete_cache=(60, 60)) as demo:
    gr.Markdown("# Health Journey · InBody Hub")
    if os.getenv("SPACE_ID") and OAUTH_URLS and not anonymous_demo_requested():
        gr.HTML(
            '<div style="padding:0.4rem 0">'
            '¿Necesitas guardar en Neon? Evita la pantalla blanca del login incrustado: '
            f'<a href="{OAUTH_URLS["login"]}" target="_blank" '
            'rel="noopener noreferrer">Iniciar sesión en pestaña nueva</a>. '
            f'<a href="{OAUTH_URLS["app"]}" target="_blank" '
            'rel="noopener noreferrer">Abrir aplicación independiente</a>.'
            '</div>'
        )
    with gr.Tab("InBody Upload"):
        from inbody_mvp.gemini_review import (
            COLUMNS as GEMINI_COLUMNS, extract_gemini, review_status,
            save_audit,
        )
        gr.Markdown(
            "### InBody Hub · Gemini Flash\n"
            "Carga un PDF o imagen, extrae las mediciones y revisa **cada fila**. "
            "El visor de secciones se ha retirado. No se extraen historiales. "
            "**Privacidad:** en un Space público, utiliza únicamente reportes anonimizados. "
            "Gemini procesa la imagen en el servicio de Google."
        )
        gemini_upload = gr.File(
            label="Reporte InBody", file_types=[".pdf", ".jpg", ".jpeg", ".png"],
            type="filepath",
        )
        gemini_upload_state = gr.State(value=None)
        gemini_snapshot = gr.State(value=None)
        gemini_upload.change(
            fn=snapshot_upload, inputs=[gemini_upload], outputs=[gemini_upload_state],
        ).then(fn=lambda: None, outputs=[gemini_snapshot])
        gemini_extract = gr.Button("Extraer mediciones con Gemini Flash", variant="primary")
        gemini_status = gr.Markdown("Pendiente de extracción.")
        gr.Markdown(
            "### Revisar y corregir mediciones\n"
            "La columna **original_value** es el valor obtenido por Gemini y no se modifica. "
            "Edita **value**, **unit**, **section** o **measurement** cuando corresponda. "
            "Si cambias algo, debes escribir **correction_comment**. "
            "Marca **reviewed** en TODAS las filas, incluso cuando Gemini acertó. "
            "La columna **was_corrected** se calcula automáticamente al guardar."
        )
        gemini_table = gr.Dataframe(
            headers=GEMINI_COLUMNS,
            datatype=["str","str","str","number","str","str","str","str",
                      "str","bool","str","bool"],
            type="pandas", interactive=True,
            static_columns=[0,1,2,3,8,9],
            label="Revisión de mediciones; una fila por valor",
        )
        gemini_extract.click(
            fn=extract_gemini, inputs=[gemini_upload_state],
            outputs=[gemini_table, gemini_snapshot, gemini_status],
            concurrency_limit=1,
        )
        gemini_check = gr.Button("Validar revisión y correcciones", variant="secondary")
        gemini_check.click(
            fn=review_status, inputs=[gemini_table, gemini_snapshot],
            outputs=[gemini_status],
        )
        gr.Markdown(
            "### Guardar auditoría en Neon\n"
            "El guardado requiere autenticación autorizada, consentimiento y la "
            "migración SQL 004. Se conserva el valor original y el final, el "
            "comentario y si hubo corrección. El historial/dashboard existente "
            "no se modifica automáticamente en esta etapa."
        )
        gemini_consent = gr.Checkbox(label="Autorizo guardar la auditoría privada en Neon", value=False)
        gemini_save = gr.Button(
            "Guardar mediciones revisadas y auditoría",
            interactive=database_enabled(), variant="primary",
        )
        gemini_save_status = gr.Markdown()
        gemini_save.click(
            fn=save_audit,
            inputs=[gemini_table, gemini_snapshot, gemini_consent],
            outputs=[gemini_save_status],
            concurrency_limit=1,
        )
        gr.ClearButton(
            [gemini_upload, gemini_upload_state, gemini_snapshot,
             gemini_table, gemini_status, gemini_consent, gemini_save_status],
            value="Limpiar",
        )
    with gr.Tab("Dashboard público"):
        gr.Markdown(
            "**Progreso personal con identificador aleatorio.** "
            "Solo aparecen los exámenes que autorizaste al guardarlos. "
            "No se publican nombre, cédula, ID InBody, edad, hora, archivos "
            "ni texto OCR. Se muestran las fechas (sin hora) y valores "
            "de las mediciones: aunque tu ID esté oculto, los patrones "
            "pueden permitir reidentificación."
        )
        metric_public = gr.Dropdown(
            choices=[(label, metric) for metric, label in PUBLIC_METRICS.items()],
            value="weight", label="Medición que deseas visualizar",
        )
        public_button = gr.Button(
            "Ver progreso público",
            interactive=public_dashboard_enabled(),
        )
        if not public_dashboard_enabled():
            gr.Markdown(
                "Dashboard público sin conexión. En este mismo Space configura "
                "PUBLIC_DATABASE_URL (Secret de solo lectura) y "
                "ENABLE_PUBLIC_DASHBOARD=1 (Variable). La carga de archivos "
                "continuará habilitada."
            )
        public_status = gr.Markdown("Sin consulta.")
        public_plot = gr.Plot(label="Tendencias de mediciones publicadas")
        public_table = gr.Dataframe(
            label="Mediciones publicadas sin datos de identidad",
            type="pandas", interactive=False,
        )

        def show_public_dashboard(variable):
            try:
                records = load_public_person_series(variable)
            except ValueError as exc:
                raise gr.Error(str(exc)) from exc
            except Exception:
                raise gr.Error(
                    "No se pudieron consultar las mediciones públicas. "
                    "Verifica la conexión y la migración 003."
                )
            frame = pd.DataFrame(records)
            fig = go.Figure()
            if frame.empty:
                return (
                    "Todavía no hay mediciones de esta variable autorizadas "
                    "para el dashboard. Guarda un examen marcando la casilla "
                    "de publicación desde el Space privado.",
                    fig, frame,
                )
            # Never render the underlying UUID alias or raw personal identifier.
            frame["serie"] = frame["anonymous_id"].map(
                lambda alias: "Serie " + str(alias)[:8]
            )
            frame["modelo_y_region"] = frame.apply(
                lambda item: (
                    str(item["device_group"])
                    + " · " + str(item["segmento"] or "Cuerpo completo")
                    + " · " + str(item["variable_medida"])
                ),
                axis=1,
            )
            frame["linea"] = frame["serie"] + " · " + frame["modelo_y_region"]
            # Separate incomparable units, models, segments and frequencies.
            frame["linea"] = frame["linea"] + " · " + frame["unidad_medida"].fillna("?")
            fig = px.line(
                frame.sort_values("exam_date"),
                x="exam_date", y="valor_medida",
                color="linea", markers=True,
                labels={
                    "exam_date": "Fecha del examen (sin hora)",
                    "valor_medida": "Valor medido",
                    "linea": "Serie y tipo de medición",
                },
            )
            visible = frame[
                ["serie", "exam_date", "device_group", "variable_medida",
                 "unidad_medida", "segmento", "valor_medida"]
            ].copy()
            visible.columns = [
                "Serie", "Fecha", "Modelo", "Medición", "Unidad",
                "Segmento", "Valor"
            ]
            return (
                f"{len(visible)} mediciones publicadas, "
                f"{frame['serie'].nunique()} serie(s) sin ID personal.",
                fig, visible,
            )

        public_button.click(
            fn=show_public_dashboard,
            inputs=[metric_public],
            outputs=[public_status, public_plot, public_table],
            concurrency_limit=1,
        )
    with gr.Tab("Historial en Neon"):
        if anonymous_demo_requested():
            gr.Markdown(
                "**Historial privado deshabilitado en demostración.** "
                "Para verificar las mediciones publicadas, utiliza "
                "la pestaña «Dashboard público». Los datos de demostración "
                "nunca se mezclan con pacientes privados."
            )
        else:
            gr.Markdown(
                "Consulta únicamente con una cuenta autorizada. "
                "Selecciona el ID exacto que aparece en el reporte. "
                "Las tendencias son exploratorias y no prueban mejoría clínica."
            )
        history_id = gr.Textbox(label="ID de persona en InBody", placeholder="ID exacto")
        with gr.Row():
            metric_filter = gr.Dropdown(
                choices=[
                    "weight", "skeletal_muscle_mass", "body_fat_mass",
                    "body_fat_percentage", "segmental_lean_mass",
                    "segmental_fat_mass", "phase_angle",
                ],
                value="weight", label="Medida para la tendencia",
            )
            unit_filter = gr.Textbox(value="kg", label="Unidad exacta")
            segment_filter = gr.Dropdown(
                choices=[
                    ("Cuerpo completo / sin segmento", ""),
                    ("Brazo izquierdo", "left_arm"),
                    ("Brazo derecho", "right_arm"),
                    ("Pierna izquierda", "left_leg"),
                    ("Pierna derecha", "right_leg"),
                    ("Tronco", "trunk"),
                ],
                value="", label="Región corporal",
            )
        load_button = gr.Button(
            "Consultar Neon", interactive=not anonymous_demo_requested()
        )
        db_status = gr.Markdown("Sin consulta.")
        db_chart = gr.Plot(label="Tendencia de medidas confirmadas")
        db_table = gr.Dataframe(
            label="Detalle de mediciones confirmadas", interactive=False,
            type="pandas",
        )

        def display_history(
            person_id, metric, unit, segment,
            profile: gr.OAuthProfile | None = None,
        ):
            try:
                records = load_measurement_history(
                    person_id, oauth_profile=profile, limit=500
                )
            except (PermissionError, ValueError) as exc:
                raise gr.Error(str(exc)) from exc
            except Exception:
                raise gr.Error("No se pudo consultar Neon. Revisa la conexión y los permisos.")
            frame = pd.DataFrame(records)
            fig = go.Figure()
            if frame.empty:
                return "No se encontraron mediciones para ese ID.", fig, frame
            selected = frame[
                (frame["variable_medida"] == metric)
                & (frame["unidad_medida"] == unit)
                & (frame["segmento"].fillna("") == (segment or ""))
            ].copy()
            if not selected.empty:
                selected["series_name"] = selected.apply(
                    lambda item: (
                        str(item["modelo_inbody"] or "Modelo desconocido")
                        + " | " + str(item["variable_medida"])
                    ),
                    axis=1,
                )
                selected = selected.sort_values("exam_timestamp")
                fig = px.line(
                    selected, x="exam_timestamp", y="valor_medida",
                    color="series_name", markers=True,
                    labels={"exam_timestamp": "Fecha del examen",
                            "valor_medida": unit, "series_name": "Modelo y medición"},
                    title=f"{metric} — {unit}",
                )
            return (
                f"{len(frame)} mediciones encontradas (máximo 500 por consulta). "
                "Separadas por modelo y variable para evitar series incompatibles.",
                fig, frame
            )

        load_button.click(
            fn=display_history,
            inputs=[history_id, metric_filter, unit_filter, segment_filter],
            outputs=[db_status, db_chart, db_table],
            concurrency_limit=1,
        )
    with gr.Tab("Dashboard (siguiente fase)"):
        gr.Markdown(
            "El dashboard se construirá en **Gradio + Plotly** después de verificar "
            "y almacenar mediciones confirmadas. Tendrá filtros por fecha, variable, "
            "unidad y región corporal, con tendencias y ángulo de fase. "
            "Esta versión todavía no presenta series históricas."
        )
    with gr.Tab("Proyecto"):
        gr.Markdown(value=read_readme)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1", server_port=int(os.environ.get("PORT", "7860")), share=False, ssr_mode=False)
