"""Health Journey: Gemini InBody extraction, human review and private audit.

In public QA Spaces use only synthetic or anonymized reports. Private Neon
operations require explicitly authorized Hugging Face OAuth sessions.
"""
from __future__ import annotations

import os
from pathlib import Path

import spaces  # ZeroGPU startup requires a registered GPU handler.
import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv(override=False)  # Local-only .env; do not commit credentials.

from inbody_mvp.extractor import DocumentError, MAX_UPLOAD_BYTES
from inbody_mvp.public_dashboard import (
    PUBLIC_METRICS, public_dashboard_enabled, load_public_person_series,
)
from inbody_mvp.progress_dashboard import METRICS, SECTIONS, render_progress
from inbody_mvp.app_auth import (
    authenticate_master_demo, password_login_enabled, change_master_demo_password,
)
from inbody_mvp.oauth_ui import standalone_oauth_urls
from inbody_mvp.demo_storage import anonymous_demo_requested
from inbody_mvp.storage import (
    database_enabled, require_database_access, load_measurement_history,
    load_reviewed_audit_history,
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



def popup_error(exc: Exception, fallback: str = "No se pudo completar la operación.") -> None:
    """One Gradio toast per error; never write an error into an output component.

    Expected UI/validation errors have safe user-facing text. Internal errors
    are deliberately generic to avoid exposing document contents or DB secrets.
    """
    if isinstance(exc, (gr.Error, ValueError, PermissionError, DocumentError)):
        message = getattr(exc, "message", None) or str(exc).strip("'\\\"")
    else:
        message = fallback
    gr.Warning(str(message))


def keep_components(count: int):
    """Preserve existing file, review, plots and status on a failed event."""
    return tuple(gr.update() for _ in range(count))



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
        raise DocumentError("No se pudo recibir el archivo. Vuelve a cargarlo.") from exc


def verify_neon_session(
    profile: gr.OAuthProfile | None = None, request: gr.Request | None = None
) -> str:
    """Only checks HF OAuth and allowlist, never contacts Neon or logs secrets."""
    try:
        require_database_access(profile, request=request)
    except PermissionError:
        gr.Warning(
            "No hay sesión de aplicación o Hugging Face autorizada para Neon. "
            "Inicia sesión con la cuenta autorizada."
        )
        return gr.update()
    return (
        "Sesión autorizada para operaciones privadas. "
        "La conexión SQL todavía no ha sido comprobada."
    )


@spaces.GPU(duration=15)
def diagnose_zerogpu() -> str:
    """Optional real CUDA diagnostic. Normal Gemini extraction does not use GPU."""
    import torch

    if not torch.cuda.is_available():
        return "No hay GPU CUDA disponible para el diagnóstico."
    tensor = torch.ones(8, device="cuda")
    result = float(tensor.sum().item())
    return f"ZeroGPU disponible: {torch.cuda.get_device_name(0)} (prueba CUDA: {result:g})."


OAUTH_URLS = standalone_oauth_urls(os.getenv("SPACE_HOST"))

with gr.Blocks(title="Health Journey", analytics_enabled=False, delete_cache=(60, 60)) as demo:
    gr.Markdown("# Health Journey · InBody Hub")
    if password_login_enabled():
        gr.Markdown(
            "**Acceso protegido:** has iniciado sesión con el usuario de "
            "la aplicación. El historial privado sigue sujeto a permisos "
            "del servidor; cerrar sesión termina el acceso a los módulos."
        )
        with gr.Accordion("Seguridad de la cuenta (cambiar contraseña)", open=False):
            gr.Markdown(
                "Después del primer acceso, cambia la contraseña inicial. "
                "Utiliza al menos 16 caracteres; no compartas contraseñas "
                "en GitHub ni en capturas de pantalla."
            )
            current_login_password = gr.Textbox(
                label="Contraseña actual", type="password"
            )
            next_login_password = gr.Textbox(
                label="Nueva contraseña", type="password"
            )
            confirm_login_password = gr.Textbox(
                label="Confirmar nueva contraseña", type="password"
            )
            change_login_button = gr.Button("Actualizar contraseña")
            change_login_result = gr.Markdown()

            def change_login(
                old_password, new_password, confirm_password,
                request: gr.Request | None = None,
            ):
                try:
                    return change_master_demo_password(
                        old_password, new_password, confirm_password, request
                    )
                except Exception as exc:
                    popup_error(exc, "No se pudo cambiar la contraseña.")
                    return gr.update()

            change_login_button.click(
                fn=change_login,
                inputs=[
                    current_login_password, next_login_password,
                    confirm_login_password,
                ],
                outputs=[change_login_result],
                concurrency_limit=1,
            )
    # The optional GPU callback keeps an existing ZeroGPU Space compatible.
    # It is NEVER invoked by the Gemini API or Neon audit workflows.
    with gr.Accordion("Diagnóstico ZeroGPU (opcional)", open=False):
        gr.Markdown(
            "Solo para verificar el hardware de Hugging Face. "
            "Ejecutarlo consume cuota GPU; las extracciones con Gemini no la utilizan."
        )
        gpu_diagnostic_button = gr.Button("Probar GPU disponible")
        gpu_diagnostic_result = gr.Textbox(label="Resultado", interactive=False)
        def diagnose_gpu_with_popup():
            try:
                result = diagnose_zerogpu()
                if result.startswith("No hay GPU CUDA disponible"):
                    gr.Warning(result)
                    return gr.update()
                return result
            except Exception as exc:
                popup_error(exc, "No se pudo ejecutar el diagnóstico GPU.")
                return gr.update()

        gpu_diagnostic_button.click(
            fn=diagnose_gpu_with_popup,
            outputs=[gpu_diagnostic_result], concurrency_limit=1
        )

    with gr.Tab("InBody Upload"):
        from inbody_mvp.gemini_review import (
            COLUMNS as GEMINI_COLUMNS, extract_gemini, review_status,
            save_audit, check_gemini_models, render_document_preview,
            check_processed_filename,
            audit_write_enabled,
        )
        gr.Markdown(
            "### InBody Hub · Gemini Flash\n"
            "Carga un PDF o imagen, extrae las mediciones y revisa **cada fila**. "
            "El visor de secciones se ha retirado. No se extraen historiales. "
            "**Secciones y mediciones normalizadas en inglés.** "
            "**Privacidad:** en un Space público, utiliza únicamente reportes anonimizados. "
            "Gemini procesa la imagen en el servicio de Google."
        )
        gr.Markdown(
            "### Consentimientos del examen\n"
            "Selecciona independientemente dónde autorizas enviar los datos. "
            "No se necesita iniciar sesión para guardar una auditoría. "
            "**En un Space público utiliza solo documentos anonimizados.**"
        )
        with gr.Row():
            gemini_consent_remote = gr.Checkbox(
                label="Autorizo enviar el documento a Google Gemini",
                value=False,
            )
            gemini_consent = gr.Checkbox(
                label="Autorizo guardar las mediciones revisadas en Neon",
                value=False,
            )
        gemini_upload = gr.File(
            label="Reporte InBody", file_types=[".pdf", ".jpg", ".jpeg", ".png"],
            type="filepath",
        )
        gemini_upload_state = gr.State(value=None)
        gemini_file_status = gr.Markdown("Sin archivo para verificar.")
        gemini_snapshot = gr.State(value=None)
        with gr.Accordion("Diagnóstico de la API de Gemini", open=False):
            gr.Markdown(
                "Comprueba qué modelos Flash permite tu API key. "
                "No se envían imágenes ni reportes en esta consulta."
            )
            gemini_models_button = gr.Button("Comprobar modelos disponibles")
            gemini_models_status = gr.Markdown()
            def check_models_with_popup():
                try:
                    result = check_gemini_models()
                    if result.startswith(
                        ("Falta GEMINI_API_KEY", "No fue posible", "Gemini (")
                    ):
                        gr.Warning(result)
                        return gr.update()
                    return result
                except Exception as exc:
                    popup_error(exc, "No fue posible consultar los modelos Gemini.")
                    return gr.update()

            gemini_models_button.click(
                fn=check_models_with_popup,
                outputs=[gemini_models_status],
            )
        gr.Markdown(
            "Al cargar el documento se comprobará si su nombre ya fue "
            "procesado (solo para una sesión privada autorizada). "
            "Al guardar se comprueban también el contenido, el ID, "
            "la fecha exacta del examen y el nombre de cada medición."
        )
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
        with gr.Row(equal_height=False):
            with gr.Column(scale=5, min_width=340):
                gr.Markdown("**Documento original** — páginas del PDF o imagen, con ampliación al seleccionar.")
                gemini_preview = gr.Gallery(
                    label="Visor PDF / imagen",
                    columns=1,
                    height=690,
                    selected_index=0,
                    preview=True,
                    allow_preview=True,
                    object_fit="contain",
                    buttons=["fullscreen"],
                    interactive=False,
                    format="png",
                )
                gemini_preview_status = gr.Markdown(
                    "Carga un PDF o imagen para visualizarlo."
                )
            with gr.Column(scale=7, min_width=550):
                gr.Markdown("**Valores extraídos** — contrasta cada fila con el documento antes de guardarla.")
                gemini_table = gr.Dataframe(
                    headers=GEMINI_COLUMNS,
                    datatype=["str","str","str","number","str","str","str","str",
                              "str","bool","str","bool"],
                    type="pandas", interactive=True,
                    static_columns=[0,1,2,3,8,9],
                    label="Revisión de mediciones; una fila por valor",
                )
        def extract_with_popup(state, consent):
            try:
                return extract_gemini(state, consent)
            except Exception as exc:
                popup_error(exc, "No se pudo extraer el reporte.")
                return keep_components(3)

        gemini_extract.click(
            fn=extract_with_popup,
            inputs=[gemini_upload_state, gemini_consent_remote],
            outputs=[gemini_table, gemini_snapshot, gemini_status],
            concurrency_limit=1,
        )
        gemini_check = gr.Button("Validar revisión y correcciones", variant="secondary")
        def review_with_popup(table, snapshot):
            try:
                result = review_status(table, snapshot)
                if result.startswith("Revisión pendiente:"):
                    gr.Warning(result.removeprefix("Revisión pendiente:").strip())
                    return gr.update()
                return result
            except Exception as exc:
                popup_error(exc, "No se pudo validar la revisión.")
                return gr.update()

        gemini_check.click(
            fn=review_with_popup,
            inputs=[gemini_table, gemini_snapshot],
            outputs=[gemini_status],
        )
        gr.Markdown(
            "### Guardar auditoría en Neon\n"
            "Se utiliza el consentimiento marcado al inicio y una conexión "
            "restringida de solo escritura. No se requiere login para enviar, "
            "pero el historial privado continúa protegido."
        )
        if not audit_write_enabled():
            gr.Markdown(
                "El guardado requiere configurar el Secret `DEMO_DATABASE_URL` "
                "y `ENABLE_ANONYMOUS_DEMO=1`. No uses DATABASE_URL de administrador."
            )
        gemini_overwrite = gr.Checkbox(
            label="Confirmo sobrescribir mediciones anteriores cuando "
                  "coincidan persona, fecha del examen y medición",
            value=False,
        )
        gemini_save = gr.Button(
            "Guardar mediciones revisadas y auditoría",
            interactive=audit_write_enabled(), variant="primary",
        )
        gemini_save_status = gr.Markdown()

        def save_review_and_clear(table, snapshot, consent, overwrite):
            try:
                message = save_audit(table, snapshot, consent, overwrite)
            except Exception as exc:
                popup_error(exc, "No se pudo guardar la auditoría en Neon.")
                return keep_components(12)
            if message.startswith("Guardado en Neon:"):
                # One atomic UI event clears the previous file, its preview,
                # the AI snapshot, the editable table and both consents.
                gr.Info(message)
                return (
                    "", None, None, None, [], "Carga un PDF o imagen para visualizarlo.",
                    pd.DataFrame(columns=GEMINI_COLUMNS),
                    "Pendiente de extracción.", False, False, False,
                    "Sin archivo para verificar.",
                )
            gr.Warning(message)
            return keep_components(12)

        gemini_save.click(
            fn=save_review_and_clear,
            inputs=[gemini_table, gemini_snapshot, gemini_consent, gemini_overwrite],
            outputs=[
                gemini_save_status, gemini_upload, gemini_upload_state,
                gemini_snapshot, gemini_preview, gemini_preview_status,
                gemini_table, gemini_status, gemini_consent,
                gemini_consent_remote, gemini_overwrite, gemini_file_status,
            ],
            concurrency_limit=1,
        )
        # Reset all previous-review state when a different file is selected.
        # The preview runs locally and does not require Gemini consent.
        # User upload event only: clearing after a successful save must not
        # trigger another reset that hides the saved confirmation.
        def show_processed_filename(
            state, profile: gr.OAuthProfile | None = None,
            request: gr.Request | None = None,
        ):
            try:
                message = check_processed_filename(
                    state, profile=profile, request=request
                )
                if message.startswith(("Este nombre de archivo ya fue procesado",
                                       "No se pudo leer", "La verificación anticipada no")):
                    gr.Warning(message)
                    return gr.update()
                return message
            except Exception as exc:
                popup_error(exc, "No se pudo comprobar el nombre del archivo.")
                return gr.update()

        def upload_with_popup(file_path):
            try:
                return snapshot_upload(file_path)
            except Exception as exc:
                popup_error(exc, "No se pudo recibir el archivo.")
                return gr.update()

        def preview_with_popup(state):
            try:
                return render_document_preview(state)
            except Exception as exc:
                popup_error(exc, "No se pudo mostrar el documento.")
                return keep_components(2)

        gemini_upload.upload(
            fn=upload_with_popup,
            inputs=[gemini_upload],
            outputs=[gemini_upload_state],
        ).then(
            fn=lambda: (None, False),
            outputs=[gemini_snapshot, gemini_consent_remote],
        ).then(
            fn=lambda: (
                pd.DataFrame(columns=GEMINI_COLUMNS),
                "Pendiente de extracción.", False, ""
            ),
            outputs=[gemini_table, gemini_status, gemini_consent, gemini_save_status],
        ).then(
            fn=preview_with_popup,
            inputs=[gemini_upload_state],
            outputs=[gemini_preview, gemini_preview_status],
        ).then(
            fn=show_processed_filename,
            inputs=[gemini_upload_state],
            outputs=[gemini_file_status],
        )
        gr.ClearButton(
            [gemini_upload, gemini_upload_state, gemini_snapshot,
             gemini_preview, gemini_preview_status, gemini_table, gemini_status,
             gemini_consent, gemini_consent_remote, gemini_save_status,
             gemini_overwrite, gemini_file_status],
            value="Limpiar",
        )
    with gr.Tab("Dashboard"):
        gr.Markdown(
            "## Dashboard InBody\\n"
            "Un único lugar para visualizar el progreso histórico personal "
            "y, por separado, las mediciones autorizadas para publicación. "
            "La búsqueda privada admite el alias `test` cuando está "
            "configurado como Secret; nunca revela el ID original."
        )
        with gr.Accordion("Mi progreso histórico (acceso privado)", open=True):
            gr.Markdown(
                "## Progreso histórico InBody\\n"
                "Consulta las mediciones **revisadas y guardadas en Neon** con "
                "acceso privado autorizado. La persona se presenta mediante "
                "un alias; la cédula del reporte no aparece en gráficas ni tablas. "
                "Los valores históricos dibujados en el PDF **no** se importan."
            )
            with gr.Row():
                progress_person = gr.Textbox(
                    label="ID del reporte (solo búsqueda privada)",
                    placeholder="ID del reporte o alias privado test",
                    type="password", scale=3,
                )
                progress_start = gr.DateTime(
                    include_time=False, type="string",
                    label="Desde", scale=2,
                )
                progress_end = gr.DateTime(
                    include_time=False, type="string",
                    label="Hasta", scale=2,
                )
            progress_refresh = gr.Button(
                "Consultar progreso", variant="primary",
                interactive=database_enabled(),
            )
            if not database_enabled():
                gr.Markdown(
                    "Para consultar historiales de auditoría, configura "
                    "`ENABLE_PERSISTENCE=1`, `DATABASE_URL` y `HF_ALLOWED_USERS`. "
                    "Aunque el modo demo permita guardar sin login, el acceso "
                    "al historial personal exige OAuth autorizado."
                )
            gr.Markdown(
                "**Valores actuales** — cada flecha de Plotly muestra si la "
                "medición subió o bajó y su diferencia porcentual contra la "
                "fecha anterior **dentro del rango elegido**. "
                "Las flechas son descriptivas, no indican si un cambio es saludable."
            )
            progress_status = gr.Markdown("Sin consulta.")
            with gr.Row():
                progress_kpis = [
                    gr.Plot(label=label, min_width=205)
                    for _, label, _ in METRICS
                ]
            gr.Markdown("### Historical Progress")
            gr.Markdown(
                "### Body Composition History — formato del reporte InBody\\n"
                "Filas alineadas por fecha con valores, líneas de evolución "
                "y comparación frente al examen anterior. Incluye ángulo de fase "
                "cuando esté disponible en las mediciones revisadas."
            )
            progress_trends = gr.Plot(label="Body Composition History")
            gr.Markdown("### InBody Score — progreso entre exámenes")
            progress_score = gr.Plot(label="Puntaje de cada examen · puntos")
            progress_summary = gr.Dataframe(
                label="Mediciones por fecha y cambio porcentual",
                type="pandas", interactive=False,
            )
            gr.Markdown(
                "### Detailed Exam Analysis\\n"
                "Se toma automáticamente la medición más reciente de cada "
                "variable en el rango seleccionado, y se compara con la anterior. "
                "**No es necesario escoger un examen.**"
            )
            progress_section = gr.Dropdown(
                label="Sección del reporte",
                choices=list(SECTIONS), value=SECTIONS[0],
            )
            progress_detail = gr.Dataframe(
                label="Valores actuales y comparación por sección",
                type="pandas", interactive=False,
            )
            progress_detail_plot = gr.Plot(
                label="Comparación de medidas de la sección"
            )
            progress_section_history = gr.Plot(
                label="Historial de medidas de la sección seleccionada"
            )

            def show_progress(
                person_id, start_date, end_date, section,
                profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    records = load_reviewed_audit_history(
                        person_id, oauth_profile=profile, limit=5000, request=request
                    )
                    result = render_progress(records, start_date, end_date, section)
                except Exception as exc:
                    popup_error(
                        exc, "No se pudo consultar el progreso privado en Neon."
                    )
                    return keep_components(13)
                if records:
                    alias = "Persona " + str(records[0]["anonymous_id"])[:8]
                    return (f"**{alias}** · " + result[0], *result[1:])
                return result

            progress_refresh.click(
                fn=show_progress,
                inputs=[progress_person, progress_start, progress_end, progress_section],
                outputs=[progress_status, *progress_kpis, progress_trends,
                         progress_summary, progress_detail, progress_detail_plot,
                         progress_score, progress_section_history],
                concurrency_limit=1,
            )
        with gr.Accordion("Mediciones publicadas (solo datos aprobados)", open=False):
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
                except Exception as exc:
                    popup_error(exc, "No se pudieron consultar las mediciones públicas.")
                    return keep_components(3)
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
        if os.getenv("SPACE_ID") and OAUTH_URLS:
            gr.HTML(
                "El historial privado sí requiere una sesión autorizada. "
                f'<a href="{OAUTH_URLS["login"]}" target="_blank" '
                'rel="noopener noreferrer">Iniciar sesión</a>.'
            )
        if anonymous_demo_requested() and not password_login_enabled():
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
        history_id = gr.Textbox(
            label="ID del reporte (búsqueda privada; nunca se muestra en resultados)",
            placeholder="Introduce el ID del reporte", type="password",
        )
        with gr.Accordion("Auditoría Gemini — identificador seudónimo", open=True):
            gr.Markdown(
                "El ID original se usa únicamente para buscar en Neon. "
                "En la tabla y el gráfico se muestra un alias aleatorio "
                "estable, sin archivo, edad ni hora exacta. "
                "Solo usuarios autorizados pueden consultar estas auditorías."
            )
            audit_metric = gr.Textbox(
                value="Weight", label="Measurement (English, para la gráfica)"
            )
            audit_button = gr.Button(
                "Consultar mediciones Gemini revisadas",
                interactive=(not anonymous_demo_requested() or password_login_enabled()),
            )
            audit_status = gr.Markdown("Sin consulta.")
            audit_chart = gr.Plot(label="Evolución de mediciones revisadas")
            audit_table = gr.Dataframe(
                label="Auditorías (solo alias)", type="pandas",
                interactive=False,
            )

            def display_audit_history(
                person_id, metric,
                profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    records = load_reviewed_audit_history(
                        person_id, oauth_profile=profile, limit=500, request=request
                    )
                except Exception as exc:
                    popup_error(exc, "No se pudo consultar la auditoría privada.")
                    return keep_components(3)
                fig = go.Figure()
                frame = pd.DataFrame(records)
                if frame.empty:
                    return "No se encontraron auditorías.", fig, frame
                alias = "Persona " + frame.iloc[0]["anonymous_id"][:8]
                frame["Persona"] = alias
                visible = frame[
                    ["Persona", "exam_date", "section", "measurement",
                     "value", "unit", "was_corrected"]
                ].copy()
                visible.columns = [
                    "Persona", "Fecha", "Section", "Measurement",
                    "Value", "Unit", "Corrected",
                ]
                values = frame[frame["measurement"] == str(metric).strip()].copy()
                if not values.empty:
                    values["numeric_value"] = pd.to_numeric(
                        values["value"].astype(str).str.replace(",", ".", regex=False),
                        errors="coerce",
                    )
                    values = values.dropna(subset=["numeric_value"])
                    if not values.empty:
                        fig = px.line(
                            values.sort_values("exam_date"),
                            x="exam_date", y="numeric_value",
                            color="unit", markers=True,
                            title=f"{alias} — {metric}",
                            labels={"exam_date": "Fecha", "numeric_value": "Valor"},
                        )
                return f"{alias}: {len(visible)} mediciones revisadas.", fig, visible

            audit_button.click(
                fn=display_audit_history,
                inputs=[history_id, audit_metric],
                outputs=[audit_status, audit_chart, audit_table],
                concurrency_limit=1,
            )
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
            "Consultar Neon", interactive=(not anonymous_demo_requested() or password_login_enabled())
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
            request: gr.Request | None = None,
        ):
            try:
                records = load_measurement_history(
                    person_id, oauth_profile=profile, limit=500, request=request
                )
            except Exception as exc:
                popup_error(exc, "No se pudo consultar Neon. Revisa la conexión y los permisos.")
                return keep_components(3)
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
    with gr.Tab("Proyecto"):
        gr.Markdown(value=read_readme)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1",
        server_port=int(os.environ.get("PORT", "7860")),
        share=False,
        ssr_mode=False,
        auth=authenticate_master_demo if password_login_enabled() else None,
        auth_message=(
            "Health Journey · Inicia sesión con el usuario obs-master-demo "
            "y su contraseña privada. La sesión protege todos los módulos."
        ) if password_login_enabled() else None,
    )
