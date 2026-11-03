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
from starlette.middleware import Middleware
from starlette.routing import Route

load_dotenv(override=False)  # Local-only .env; do not commit credentials.

from inbody_mvp.extractor import DocumentError, MAX_UPLOAD_BYTES
from inbody_mvp.public_dashboard import (
    PUBLIC_METRICS, public_dashboard_enabled, load_public_person_series,
)
from inbody_mvp.progress_dashboard import METRICS, SECTIONS, render_progress
from inbody_mvp.app_auth import authenticate_master_demo, password_login_enabled
from inbody_mvp.login_view import LOGIN_AUTH_MESSAGE
from inbody_mvp.inbody_flow import (
    INBODY_FLOW_CSS, INBODY_NEXT_STEP_JS, render_inbody_flow,
)
from inbody_mvp.navigation import SIDEBAR_CSS, NAV_SECTIONS
from inbody_mvp.coach_chat_ui import COACH_CHAT_CSS, COACH_CHAT_HEADER_HTML
from inbody_mvp.upload_preflight import preflight_processed_upload
from inbody_mvp.chat_session import enqueue_user_message, append_assistant_message
from inbody_mvp.project_overview import PROJECT_OVERVIEW
from inbody_mvp.ai_coach import (
    answer_coach_question, coach_model_choices, default_coach_model,
    SUPPORTED_WINDOWS,
)
from inbody_mvp.prelogin_consent import (
    PrivacyFirstMiddleware, privacy_page, submit_consent, verify_consent_session,
    current_choices, coach_choice, has_consent,
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
                return "".join(lines[index + 1:]).lstrip().replace("Neon", "base de datos")
    return text.replace("Neon", "base de datos")



def popup_error(exc: Exception, fallback: str = "No se pudo completar la operación.") -> None:
    """One Gradio toast per error; never write an error into an output component.

    Expected UI/validation errors have safe user-facing text. Internal errors
    are deliberately generic to avoid exposing document contents or DB secrets.
    """
    if isinstance(exc, (gr.Error, ValueError, PermissionError, DocumentError)):
        message = getattr(exc, "message", None) or str(exc).strip("'\\\"")
    else:
        message = fallback
    gr.Warning(str(message).replace("Neon", "la base de datos"))


# Gradio 6 draws small per-component validation banners in addition to the
# application-level alert. Keep a single toast/status and suppress only these
# redundant validation badges. Never hide inputs, labels, or toast modals.
SINGLE_ERROR_MESSAGE_CSS = """
.gradio-container div.validation-error {
    display: none !important;
}
"""


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
            "No hay sesión de aplicación o Hugging Face autorizada para la base de datos. "
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

with gr.Blocks(
    title="Health Journey", analytics_enabled=False,
    delete_cache=(60, 60),
) as demo:
    # Infrastructure-only: this invisible registered handler is required by
    # existing ZeroGPU hardware. It never runs during Gemini extraction.
    # Keep it mounted so the Space boots, but show no technical controls to
    # end users; api_name=False also avoids exposing a diagnostic endpoint.
    with gr.Column(visible=False):
        _zerogpu_keepalive = gr.Button(visible=False)
        _zerogpu_keepalive.click(
            fn=diagnose_zerogpu, outputs=[], api_name=False,
            concurrency_limit=1,
        )

    # Independent top-level viewport navbar: no scrolling parent can trap
    # a position:fixed descendant. It is hidden on all non-InBody modules.
    with gr.Column(visible=False, elem_id="hj-inbody-fixedbar") as inbody_navbar:
        inbody_flow = gr.HTML(
            value=render_inbody_flow(1),
            elem_id="hj-inbody-flow",
        )

    # Only the vertical navigation is rendered. No Gradio Tab overflow (ellipsis).
    # Mounted Gradio Columns preserve extraction/chat state while navigating.
    with gr.Sidebar(label="Menú principal", open=True, width=284,
                    elem_id="hj-module-sidebar"):
        gr.Markdown("### Health Journey")
        gr.Markdown("Elige el módulo que necesitas.", elem_classes="hj-sidebar-description")
        nav_project = gr.Button("Proyecto", variant="primary",
                                elem_classes="hj-nav-button")
        nav_inbody = gr.Button("Extractor de InBody", variant="secondary",
                               elem_classes="hj-nav-button")
        nav_training = gr.Button("Captador de logs de entrenamiento", variant="secondary",
                                 elem_classes="hj-nav-button")
        nav_coach = gr.Button("Chat con el asistente fitness", variant="secondary",
                              elem_classes="hj-nav-button")

    # All three optional consents are explained and explicitly selected
    # BEFORE Gradio login at /privacy. There are no duplicate checkboxes
    # after login. Gradio States simply mirror that signed server-side choice;
    # callbacks still verify has_consent(request, scope) on every operation.
    session_ai_consent = gr.State(value=False)
    session_db_consent = gr.State(value=False)
    session_coach_consent = gr.State(value=False)

    def restore_session_consents(request: gr.Request):
        ai, db = current_choices(request)
        return ai, db, coach_choice(request)


    with gr.Column(elem_id="hj-module-content"):
        with gr.Column(visible=True, elem_id="hj-panel-project") as project_panel:
            gr.Markdown(PROJECT_OVERVIEW)
        with gr.Column(visible=False, elem_id="hj-panel-inbody") as inbody_panel:
            from inbody_mvp.gemini_review import (
                COLUMNS as GEMINI_COLUMNS, DISPLAY_COLUMNS as GEMINI_DISPLAY_COLUMNS,
                compact_review_table, header_for_review,
                extract_gemini, review_status,
                reconcile_native_review_rows, sync_review_corrections,
                save_audit, get_free_inbody_models, render_document_preview,
                check_processed_filename,
                audit_write_enabled,
            )
            # Top-level viewport navbar is displayed only for InBody.
            # #hj-panel-inbody reserves vertical space for its fixed height.
            inbody_navigation_target = gr.State("")
            gr.Markdown("## InBody · Registrar un examen", elem_id="hj-inbody-title")
            gr.Markdown(
                "Sigue los pasos en orden: **cargar → extraer → revisar → validar → guardar**. "
                "Puedes consultar el documento original en cualquier momento. "
                "Las mediciones se guardan únicamente después de tu revisión."
            )
            gr.Markdown(
                "### 1. Carga tu examen\n"
                "Selecciona un archivo **PDF, JPG o PNG** de InBody. "
                "La aplicación mostrará una vista previa y, si tienes una sesión "
                "autorizada, comprobará si el nombre del archivo ya se procesó. "
                "**Todavía no se enviará a la IA ni se guardará en la base de datos.**",
                elem_id="hj-inbody-step-1"
            )
            gemini_upload = gr.File(
                label="Seleccionar examen InBody (PDF o imagen)",
                file_types=[".pdf", ".jpg", ".jpeg", ".png"],
                type="filepath",
            )
            gemini_upload_state = gr.State(value=None)
            gemini_upload_preflight = gr.State(value=None)
            gemini_file_status = gr.Markdown("Sin archivo seleccionado.")
            gemini_snapshot = gr.State(value=None)
            with gr.Group(elem_id="hj-ai-extraction"):
                gr.Markdown(
                    "### 2. Selecciona la IA y extrae las mediciones\n"
                    "Comprueba que activaste el **permiso para enviar datos a la IA** "
                    "en el apartado de privacidad, antes de continuar. "
                    "Elige un modelo y pulsa **Extraer mediciones**. "
                    "Google Gemini recibirá el documento solo cuando solicites la extracción.",
                    elem_id="hj-inbody-step-2"
                )
                with gr.Row():
                    gemini_model_selector = gr.Dropdown(
                        label="Modelo de IA para la extracción",
                        choices=[], value=None,
                        interactive=True, scale=4,
                        info="Solo modelos compatibles con el procesamiento de imágenes.",
                    )
                    gemini_models_button = gr.Button(
                        "Actualizar lista de modelos", scale=1,
                    )
                gemini_models_status = gr.Markdown(
                    "Se consultan los modelos disponibles sin enviar el examen. "
                    "Free Tier tiene cuotas de uso; revisa si tu proyecto "
                    "tiene facturación activa."
                )

                def check_models_with_popup():
                    try:
                        options = get_free_inbody_models()
                        ids = [model for _, model in options]
                        configured = os.getenv("GEMINI_MODEL", "").strip()
                        preferred = configured if configured in ids else (
                            "gemini-3.8-flash" if "gemini-3.8-flash" in ids else ids[0]
                        )
                        return (
                            gr.update(choices=options, value=preferred),
                            f"{len(options)} modelo(s) compatible(s) disponible(s). "
                            "Se recomienda Flash para tablas complejas. "
                            "Revisa las cuotas y el nivel de facturación del proyecto.",
                        )
                    except Exception as exc:
                        popup_error(exc, "No se pudieron consultar los modelos Gemini.")
                        return keep_components(2)

                gemini_models_button.click(
                    fn=check_models_with_popup,
                    outputs=[gemini_model_selector, gemini_models_status],
                    concurrency_limit=1,
                )
                gemini_extract = gr.Button(
                    "Extraer mediciones con IA", variant="primary",
                    interactive=False,
                )
                gemini_status = gr.Markdown(
                    "Esperando extracción. Carga un archivo y selecciona un modelo."
                )
            gr.Markdown(
                "### 3. Revisa y corrige los resultados\n"
                "Compara las mediciones extraídas con el documento original "
                "**al lado de la tabla**, sin cambiar de pantalla. "
                "Puedes ampliar las páginas del examen para verificar los valores.",
                elem_id="hj-inbody-step-3"
            )
            gr.Markdown(
                "#### Datos generales del examen\\n"
                "Los datos siguientes se aplican a **todas las mediciones**. "
                "Corrige fecha, ID o edad **una sola vez**. El nombre del "
                "archivo original se conserva sin modificaciones."
            )
            with gr.Row():
                header_exam_datetime = gr.Textbox(
                    label="Fecha y hora del examen",
                    placeholder="YYYY-MM-DD HH:MM:SS",
                    info="Usa la fecha y hora exactas del reporte.",
                    min_width=200,
                )
                header_person_id = gr.Textbox(
                    label="ID de persona",
                    info="Conserva los ceros iniciales si los tiene.",
                    min_width=170,
                )
                header_age = gr.Textbox(
                    label="Edad en el examen",
                    info="Número entero; puede quedar vacía.",
                    min_width=150,
                )
                header_filename = gr.Textbox(
                    label="Archivo original",
                    interactive=False,
                    info="Nombre del archivo cargado (no editable).",
                    min_width=210,
                )
            header_correction_reason = gr.Textbox(
                label="Motivo de corrección del encabezado",
                placeholder="Solo si corriges fecha, ID o edad",
                info="Se registra una sola vez y se vincula a las mediciones del examen.",
            )
            gr.Markdown(
                "**Cómo revisar las mediciones:** compara **original_value** "
                "(lectura de la IA, no editable) con **value** (valor corregible), "
                "**unit**, **measurement** y **section**. Si corriges una "
                "medición, explica el cambio en **correction_comment**. "
                "**was_corrected** se marca automáticamente cuando una medición "
                "es distinta de la lectura original. Usa el menú de la fila "
                "en la tabla para **eliminar** mediciones incorrectas, sin "
                "botones adicionales. Marca **reviewed** en cada fila "
                "conservada y pulsa **Guardar cambios**."
            )
            # Review the parsed values and their original source together.
            # The two panes stack on mobile instead of trapping the gallery
            # in a collapsed accordion. The PDF is rendered locally once.
            # Only show the review panels after a successful AI extraction.
            with gr.Row(
                elem_id="hj-inbody-review-layout", equal_height=False,
                visible=False,
            ) as inbody_review_layout:
                with gr.Column(
                    scale=7, min_width=420,
                    elem_id="hj-inbody-review-table",
                ):
                    gemini_table = gr.Dataframe(
                        headers=GEMINI_DISPLAY_COLUMNS,
                        datatype=["str", "str", "str", "str", "str", "bool", "str", "bool"],
                        type="pandas", interactive=True,
                        static_columns=[4],
                        show_row_numbers=True,
                        row_limits=(1, None),
                        label="Mediciones: edita o elimina filas en la propia tabla",
                    )
                with gr.Column(
                    scale=5, min_width=300,
                    elem_id="hj-inbody-review-document",
                ):
                    gr.Markdown(
                        "**Documento original** · cambia de página o "
                        "abre la vista completa para comprobar cada medición."
                    )
                    gemini_preview = gr.Gallery(
                        label="Visor PDF / imagen",
                        columns=1,
                        height=820,
                        selected_index=0,
                        preview=False,
                        allow_preview=True,
                        object_fit="contain",
                        buttons=["fullscreen"],
                        interactive=False,
                        format="png",
                        elem_id="hj-inbody-document-gallery",
                    )
                    gemini_preview_status = gr.Markdown(
                        "Carga un PDF o imagen para visualizarlo."
                    )
            def extract_with_popup(
                state, consent, model, preflight,
                profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    if consent is not True or not has_consent(request, "ai"):
                        raise PermissionError(
                            "Autoriza el envío a la IA antes de extraer el examen."
                        )
                    if not state or not isinstance(state.get("data"), bytes):
                        raise ValueError("Primero selecciona un examen válido.")
                    if not model:
                        raise ValueError(
                            "Selecciona un modelo Gemini disponible antes de extraer."
                        )
                    # Defensive check on the server: even a forged or stale
                    # enabled button must never reach Gemini for a known duplicate.
                    import hashlib
                    uploaded_sha = hashlib.sha256(state["data"]).hexdigest()
                    if (isinstance(preflight, dict)
                            and preflight.get("sha256") == uploaded_sha
                            and preflight.get("status") == "duplicate"):
                        raise ValueError(
                            "Este archivo ya fue procesado. No se enviará a Gemini."
                        )
                    fresh = preflight_processed_upload(
                        state, profile=profile, request=request
                    )
                    if fresh["status"] == "duplicate":
                        raise ValueError(
                            "Este archivo ya fue procesado. No se enviará a Gemini."
                        )
                    frame, snapshot, message = extract_gemini(
                        state, consent, selected_model=model
                    )
                    return (
                        compact_review_table(frame), snapshot, message,
                        *header_for_review(snapshot),
                    )
                except Exception as exc:
                    popup_error(exc, "No se pudo extraer el reporte.")
                    return keep_components(8)

            def progress_after_extract(snapshot, upload):
                if snapshot is not None:
                    return (
                        render_inbody_flow(3), "hj-inbody-step-3",
                        gr.update(visible=True),
                    )
                return (
                    render_inbody_flow(2 if upload else 1), "",
                    gr.update(visible=False),
                )

            gemini_extract.click(
                fn=extract_with_popup,
                inputs=[
                    gemini_upload_state, session_ai_consent,
                    gemini_model_selector, gemini_upload_preflight,
                ],
                outputs=[
                    gemini_table, gemini_snapshot, gemini_status,
                    header_exam_datetime, header_filename, header_person_id,
                    header_age, header_correction_reason,
                ],
                concurrency_limit=1,
            ).then(
                fn=progress_after_extract,
                inputs=[gemini_snapshot, gemini_upload_state],
                outputs=[
                    inbody_flow, inbody_navigation_target, inbody_review_layout,
                ],
                show_progress="hidden",
            ).then(
                fn=None, js=INBODY_NEXT_STEP_JS,
                inputs=[inbody_navigation_target], outputs=[],
                show_progress="hidden", queue=False, api_name=False,
            )

            gr.Markdown(
                "### 4. Valida todas las mediciones\n"
                "Edita **value** y **correction_comment** directamente en la tabla. "
                "La casilla **was_corrected** se actualiza automáticamente al "
                "comparar cada medición con su valor original. Cuando todas las "
                "filas conservadas estén marcadas como **reviewed**, pulsa "
                "**Guardar cambios** para confirmar la revisión y avanzar. "
                "Esta acción no escribe en la base de datos.",
                elem_id="hj-inbody-step-4"
            )
            gemini_check = gr.Button("Guardar cambios", variant="secondary")
            # Review status still drives the progress workflow internally,
            # but human-facing errors are delivered once via gr.Warning.
            gemini_review_status = gr.Markdown(
                "Revisión pendiente: guarda los cambios antes de continuar.",
                visible=False,
            )
            def exam_header_edits(exam_datetime, filename, person_id, age, reason):
                return {
                    "exam_datetime": exam_datetime, "filename": filename,
                    "person_id": person_id, "age": age,
                    "correction_comment": reason,
                }

            def review_with_popup(table, snapshot, exam_datetime, filename,
                                  person_id, age, reason):
                try:
                    # Reconcile native row deletion even if the user confirms
                    # before the grid's input callback finishes.
                    updated, new_snapshot = reconcile_native_review_rows(
                        table, snapshot
                    )
                    result = review_status(
                        updated, new_snapshot, header_edits=exam_header_edits(
                            exam_datetime, filename, person_id, age, reason
                        ),
                    )
                    if result.startswith("Revisión pendiente:"):
                        gr.Warning(result.removeprefix("Revisión pendiente:").strip())
                        # Clear any prior success to prevent advancing on stale
                        # validation while showing only one warning popup.
                        return updated, new_snapshot, ""
                    gr.Info("Cambios de revisión confirmados. Continúa a guardar el examen.")
                    return updated, new_snapshot, result
                except Exception as exc:
                    popup_error(exc, "No se pudieron confirmar los cambios.")
                    return gr.update(), gr.update(), ""

            def progress_after_validation(message, snapshot):
                if snapshot is None:
                    return gr.update(), ""
                if isinstance(message, str) and message.startswith("Revisión completa:"):
                    return render_inbody_flow(5), "hj-inbody-step-5"
                return render_inbody_flow(4), ""

            gemini_check.click(
                fn=review_with_popup,
                inputs=[
                    gemini_table, gemini_snapshot, header_exam_datetime,
                    header_filename, header_person_id, header_age,
                    header_correction_reason,
                ],
                outputs=[gemini_table, gemini_snapshot, gemini_review_status],
            ).then(
                fn=progress_after_validation,
                inputs=[gemini_review_status, gemini_snapshot],
                outputs=[inbody_flow, inbody_navigation_target],
                show_progress="hidden",
            ).then(
                fn=None, js=INBODY_NEXT_STEP_JS,
                inputs=[inbody_navigation_target], outputs=[],
                show_progress="hidden", queue=False, api_name=False,
            )

            def progress_after_table_edit():
                # A user correction invalidates the previous review result.
                return (
                    render_inbody_flow(3),
                    "Revisión pendiente: guarda los cambios antes de continuar.",
                )

            def sync_inline_table_edit(table, snapshot):
                try:
                    updated, new_snapshot = reconcile_native_review_rows(
                        table, snapshot
                    )
                except Exception as exc:
                    popup_error(exc, "No se pudo actualizar la tabla.")
                    return (
                        gr.update(), gr.update(),
                        render_inbody_flow(3),
                        "Revisión pendiente: guarda los cambios antes de continuar.",
                    )
                return (
                    updated, new_snapshot, render_inbody_flow(3),
                    "Revisión pendiente: guarda los cambios antes de continuar.",
                )

            # input() fires for user changes, including native row deletion,
            # without reacting to programmatic Dataframe refreshes.
            gemini_table.input(
                fn=sync_inline_table_edit,
                inputs=[gemini_table, gemini_snapshot],
                outputs=[
                    gemini_table, gemini_snapshot,
                    inbody_flow, gemini_review_status,
                ],
                trigger_mode="always_last",
                show_progress="hidden", queue=False,
            )
            for field in (
                header_exam_datetime, header_person_id, header_age,
                header_correction_reason,
            ):
                # .input is user-only; .change also fires when save clears
                # header fields programmatically and would undo the reset.
                field.input(
                    fn=progress_after_table_edit,
                    outputs=[inbody_flow, gemini_review_status],
                    show_progress="hidden", queue=False, api_name=False,
                )
            gr.Markdown(
                "### 5. Guarda el examen en la base de datos\n"
                "Activa el **permiso para guardar datos** en la sección de "
                "privacidad y pulsa **Guardar mediciones**. "
                "Se almacenarán las mediciones revisadas y el registro de auditoría. "
                "Antes de guardarlas, se verifican duplicados por archivo, "
                "identificador, fecha y medición. "
                "El permiso no publica tu examen ni envía nuevos datos a la IA.",
                elem_id="hj-inbody-step-5"
            )
            if not audit_write_enabled():
                gr.Markdown(
                    "**El guardado no está disponible en este entorno.** "
                    "Contacta al administrador de la aplicación para habilitarlo."
                )
            with gr.Accordion("Opcional: actualizar un examen ya registrado", open=False):
                gr.Markdown(
                    "Déjalo sin marcar para evitar reemplazar valores existentes. "
                    "Marca la opción solo cuando hayas comprobado que deseas "
                    "actualizar las mediciones de la misma persona y fecha."
                )
                gemini_overwrite = gr.Checkbox(
                    label="Confirmo sobrescribir mediciones anteriores cuando "
                          "coincidan persona, fecha del examen y medición",
                    value=False,
                )
            gemini_save = gr.Button(
                "Guardar mediciones revisadas",
                interactive=audit_write_enabled(), variant="primary",
            )
            gemini_save_status = gr.Markdown(
                "Sin datos guardados. Se mostrará una confirmación al completar el guardado."
            )

            def save_review_and_clear(
                table, snapshot, consent, overwrite,
                exam_datetime, filename, person_id, age, reason,
                request: gr.Request | None = None,
            ):
                try:
                    if consent is not True or not has_consent(request, "db"):
                        raise PermissionError(
                            "Autoriza guardar datos en la base de datos antes de continuar."
                        )
                    message = save_audit(
                        table, snapshot, consent, overwrite,
                        header_edits=exam_header_edits(
                            exam_datetime, filename, person_id, age, reason
                        ),
                    )
                except Exception as exc:
                    popup_error(exc, "No se pudieron guardar las mediciones en la base de datos.")
                    return keep_components(16)
                if message.startswith("Guardado en Neon:"):
                    # Show an accessible confirmation, clear the finished exam and
                    # preserve both user consents for the rest of this session.
                    visible_message = message.replace("Neon", "la base de datos")
                    gr.Info(visible_message)
                    return (
                        visible_message, None, None, None, [],
                        "Carga un PDF o imagen para visualizarlo.",
                        pd.DataFrame(columns=GEMINI_DISPLAY_COLUMNS),
                        "Esperando extracción. Carga un archivo y selecciona un modelo.",
                        False, "Sin archivo seleccionado.",
                        "Revisión pendiente: valida las filas antes de guardar.",
                        "", "", "", "", "",
                    )
                gr.Warning(message.replace("Neon", "la base de datos"))
                return keep_components(16)

            def progress_after_save(message):
                if (isinstance(message, str)
                        and message.startswith("Guardado en la base de datos:")):
                    # Keep the document visible on failed saves; hide and reset
                    # it only when the reviewed measurements were persisted.
                    return (
                        render_inbody_flow(1), "hj-inbody-step-1", "",
                        gr.update(visible=False),
                    )
                return gr.update(), "", gr.update(), gr.update()

            gemini_save.click(
                fn=save_review_and_clear,
                inputs=[
                    gemini_table, gemini_snapshot, session_db_consent,
                    gemini_overwrite, header_exam_datetime, header_filename,
                    header_person_id, header_age, header_correction_reason,
                ],
                outputs=[
                    gemini_save_status, gemini_upload, gemini_upload_state,
                    gemini_snapshot, gemini_preview, gemini_preview_status,
                    gemini_table, gemini_status, gemini_overwrite, gemini_file_status,
                    gemini_review_status,
                    header_exam_datetime, header_filename, header_person_id,
                    header_age, header_correction_reason,
                ],
                concurrency_limit=1,
            ).then(
                fn=progress_after_save,
                inputs=[gemini_save_status],
                outputs=[
                    inbody_flow, inbody_navigation_target,
                    gemini_save_status, inbody_review_layout,
                ],
                show_progress="hidden",
            ).then(
                fn=None, js=INBODY_NEXT_STEP_JS,
                inputs=[inbody_navigation_target], outputs=[],
                show_progress="hidden", queue=False, api_name=False,
            )
            # Reset all previous-review state when a different file is selected.
            # Preview runs on the application server and requires no Gemini consent.
            # User upload event only: clearing after a successful save must not
            # trigger another reset that hides the saved confirmation.
            def show_processed_filename(
                state, profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    result = preflight_processed_upload(
                        state, profile=profile, request=request
                    )
                    status = result["status"]
                    # The file-status area is the only message for duplicate
                    # or unverified uploads; do not also create warning toasts.
                    return (
                        result["message"], result,
                        gr.update(interactive=status in {"new", "unverified"}),
                    )
                except Exception as exc:
                    popup_error(exc, "No se pudo verificar el archivo seleccionado.")
                    return (
                        "", None, gr.update(interactive=False),
                    )

            def advance_after_duplicate_check(state, preflight):
                if (not state or not isinstance(preflight, dict)
                        or preflight.get("status") in {"duplicate", "empty"}):
                    return (
                        render_inbody_flow(1), "", gr.update(visible=False),
                    )
                return (
                    render_inbody_flow(2), "hj-inbody-step-2",
                    gr.update(visible=False),
                )

            def upload_with_popup(file_path):
                try:
                    return snapshot_upload(file_path), gr.update(interactive=False)
                except Exception as exc:
                    popup_error(exc, "No se pudo recibir el archivo.")
                    return None, gr.update(interactive=False)

            def preview_with_popup(state):
                try:
                    return render_document_preview(state)
                except Exception as exc:
                    popup_error(exc, "No se pudo mostrar el documento.")
                    return keep_components(2)

            gemini_upload.upload(
                fn=upload_with_popup,
                inputs=[gemini_upload],
                outputs=[gemini_upload_state, gemini_extract],
            ).then(
                fn=lambda: (None, None),
                outputs=[gemini_snapshot, gemini_upload_preflight],
            ).then(
                fn=lambda: (
                    pd.DataFrame(columns=GEMINI_DISPLAY_COLUMNS),
                    "Esperando extracción. Carga un archivo y selecciona un modelo.",
                    "", "Revisión pendiente: guarda los cambios antes de continuar.",
                    *header_for_review(None),
                ),
                outputs=[
                    gemini_table, gemini_status, gemini_save_status,
                    gemini_review_status, header_exam_datetime, header_filename,
                    header_person_id, header_age, header_correction_reason,
                ],
            ).then(
                fn=show_processed_filename,
                inputs=[gemini_upload_state],
                outputs=[
                    gemini_file_status, gemini_upload_preflight, gemini_extract,
                ],
            ).then(
                fn=preview_with_popup,
                inputs=[gemini_upload_state],
                outputs=[gemini_preview, gemini_preview_status],
            ).then(
                fn=advance_after_duplicate_check,
                inputs=[gemini_upload_state, gemini_upload_preflight],
                outputs=[
                    inbody_flow, inbody_navigation_target, inbody_review_layout,
                ],
                show_progress="hidden",
            ).then(
                fn=None, js=INBODY_NEXT_STEP_JS,
                inputs=[inbody_navigation_target], outputs=[],
                show_progress="hidden", queue=False, api_name=False,
            )
            with gr.Accordion("Progreso histórico de InBody", open=False):
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
                        "Consulta las mediciones **revisadas y guardadas en la base de datos** con "
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
                                exc, "No se pudo consultar el progreso privado en la base de datos."
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
        with gr.Column(visible=False, elem_id="hj-panel-training") as training_panel:
            from inbody_mvp.training_hub import (
                PREVIEW_COLUMNS as TRAINING_COLUMNS,
                inspect_fitnotes_upload, save_training_import, recent_training,
            )
            gr.Markdown(
                "## Training Hub · importar FitNotes\n"
                "Carga una exportación CSV de FitNotes con fecha, ejercicio, categoría, "
                "peso, repeticiones, distancia, duración y comentario. "
                "Cada fila es una serie y conserva el orden original. "
                "La importación no utiliza IA ni publica los entrenamientos. "
                "Solo se guarda en la base de datos al confirmarlo y si autorizaste "
                "el guardado en la sección de privacidad de esta sesión."
            )
            if not database_enabled():
                gr.Markdown(
                    "Para importar a la base de datos necesitas configurar la conexión privada "
                    "DATABASE_URL y un inicio de sesión autorizado."
                )
            with gr.Row():
                with gr.Column(min_width=280):
                    training_upload = gr.File(
                        label="Exportación FitNotes (.csv)", file_types=[".csv"],
                        type="filepath", interactive=database_enabled(),
                    )
                    training_summary = gr.Markdown("Sin archivo validado.")
                    training_overwrite = gr.Checkbox(
                        label="Confirmo actualizar series previamente guardadas "
                              "si sus valores cambiaron",
                        value=False,
                    )
                    training_save = gr.Button(
                        "Guardar entrenamiento en la base de datos",
                        variant="primary", interactive=database_enabled(),
                    )
                with gr.Column(min_width=300):
                    gr.Markdown(
                        "### Revisar antes de guardar\n"
                        "Se muestran las primeras 60 series. El archivo completo "
                        "se procesa únicamente cuando pulsas Guardar. "
                        "Series idénticas del mismo día se conservan si tienen "
                        "posiciones de serie diferentes."
                    )
                    training_preview = gr.Dataframe(
                        headers=list(TRAINING_COLUMNS),
                        label="Vista previa del CSV (solo lectura)",
                        type="pandas", interactive=False,
                    )
            training_state = gr.State(value=None)

            def parse_training_with_popup(
                file_path, profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    require_database_access(profile, request=request)
                    return inspect_fitnotes_upload(file_path)
                except Exception as exc:
                    popup_error(exc, "No se pudo validar el CSV de FitNotes.")
                    return keep_components(3)

            def save_training_with_popup(
                state, consent, overwrite,
                profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    if consent is not True or not has_consent(request, "db"):
                        raise PermissionError(
                            "Autoriza guardar datos en la base de datos antes de continuar."
                        )
                    result = save_training_import(
                        state, consent, overwrite, profile=profile, request=request,
                    )
                except Exception as exc:
                    popup_error(exc, "No se pudo guardar el entrenamiento en la base de datos.")
                    return keep_components(5)
                visible_result = result.replace("Neon", "la base de datos")
                gr.Info(visible_result)
                return (
                    visible_result, None, None,
                    pd.DataFrame(columns=TRAINING_COLUMNS), False,
                )

            training_upload.upload(
                fn=parse_training_with_popup, inputs=[training_upload],
                outputs=[training_state, training_summary, training_preview],
                concurrency_limit=1,
            ).then(
                fn=lambda: False,
                outputs=[training_overwrite],
            )
            training_save.click(
                fn=save_training_with_popup,
                inputs=[training_state, session_db_consent, training_overwrite],
                outputs=[
                    training_summary, training_upload, training_state,
                    training_preview, training_overwrite,
                ],
                concurrency_limit=1,
            )
            gr.Markdown(
                "### Últimas series guardadas\n"
                "La consulta solo muestra tus registros autorizados. "
                "La misma exportación no se importa dos veces."
            )
            training_refresh = gr.Button(
                "Consultar últimos entrenamientos",
                interactive=database_enabled(),
            )
            training_recent_status = gr.Markdown("Sin consulta.")
            training_recent_table = gr.Dataframe(
                headers=list(TRAINING_COLUMNS),
                label="Últimas 60 series en la base de datos", type="pandas", interactive=False,
            )

            def recent_training_with_popup(
                profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    frame = recent_training(profile=profile, request=request)
                    return f"{len(frame)} series recuperadas.", frame
                except Exception as exc:
                    popup_error(exc, "No se pudo leer el historial de entrenamiento.")
                    return keep_components(2)

            training_refresh.click(
                fn=recent_training_with_popup,
                outputs=[training_recent_status, training_recent_table],
                concurrency_limit=1,
            )

        with gr.Column(visible=False, elem_id="hj-panel-coach") as coach_panel:
            # Messaging layout: independent Gemini selector, chat header,
            # collapsible private context, chat bubbles and bottom composer.
            gr.HTML(COACH_CHAT_HEADER_HTML, elem_id="hj-chat-header-host")
            with gr.Accordion("Mis objetivos, contexto y privacidad", open=False):
                gr.Markdown(
                    "El asistente analiza mediciones InBody revisadas y "
                    "entrenamientos FitNotes **guardados** para orientar "
                    "tus metas. No reemplaza una valoración médica.\n\n"
                    "**Privacidad:** los resúmenes solo se envían a Gemini "
                    "al pulsar Enviar y con el permiso específico del chat. "
                    "No se envían documentos, identificadores de InBody, "
                    "comentarios FitNotes ni OCR bruto. La conversación "
                    "permanece únicamente en esta sesión."
                )
                with gr.Row():
                    coach_report_id = gr.Textbox(
                        label="ID del reporte InBody (consulta privada)",
                        type="password", placeholder="ID usado en tus exámenes",
                        max_lines=1, scale=2,
                    )
                    coach_window = gr.Dropdown(
                        label="Período de análisis (días)",
                        choices=list(SUPPORTED_WINDOWS), value=90, scale=1,
                    )
                coach_goals = gr.Textbox(
                    label="Mis objetivos",
                    placeholder="Por ejemplo: aumentar masa muscular y fuerza, con énfasis en piernas y hombros",
                    lines=2, max_lines=4,
                )
                coach_restrictions = gr.Textbox(
                    label="Restricciones, recuperación o molestias relevantes (opcional)",
                    placeholder="Describe solo aquello que deseas compartir con la IA",
                    lines=2, max_lines=4,
                )

            # Canonical, session-only history is separate from the visual Chatbot.
            # This prevents later Gradio events from dropping or reordering turns.
            coach_history = gr.State(value=[])
            coach_pending_question = gr.State(value="")
            coach_pending_model = gr.State(value="")
            coach_chat = gr.Chatbot(
                label=None,
                show_label=False,
                container=False,
                layout="bubble",
                height="min(64dvh, 660px)",
                elem_id="hj-coach-chatbot",
                autoscroll=True,
                placeholder="**Tu asistente fitness está listo.**\n\n"
                            "Escribe un mensaje para analizar tu progreso.",
                buttons=[],
                feedback_options=None,
            )
            with gr.Row(elem_id="hj-chat-utilities"):
                coach_context_status = gr.Markdown(
                    "Todavía no hay análisis. Empieza con una pregunta sobre tus metas.",
                    elem_id="hj-coach-data-status",
                )
                coach_clear = gr.Button(
                    "Limpiar conversación", variant="secondary", size="sm",
                    elem_id="hj-chat-clear",
                )
            # The model belongs to the same composer as the current question.
            # Freeze it for each turn so model changes cannot affect a pending call.
            with gr.Column(elem_id="hj-chat-composer"):
                coach_question = gr.Textbox(
                    label="Mensaje para el asistente",
                    show_label=False,
                    placeholder="Escribe tu mensaje...",
                    lines=1, max_lines=4, scale=8, min_width=170,
                    elem_id="hj-chat-input",
                )
                with gr.Row(elem_id="hj-chat-composer-actions"):
                    coach_model = gr.Dropdown(
                        label="Modelo Gemini para esta respuesta",
                        show_label=False,
                        choices=coach_model_choices(),
                        value=default_coach_model(),
                        interactive=True, scale=0, min_width=170,
                        elem_id="hj-chat-model",
                    )
                    coach_refresh_models = gr.Button(
                        "↻", variant="secondary", size="sm", scale=0,
                        min_width=44, elem_id="hj-chat-refresh-models",
                    )
                    coach_send = gr.Button(
                        "Enviar", variant="primary", scale=0,
                        min_width=90, elem_id="hj-chat-send",
                    )

            def coach_refresh_model_options(selected_model):
                try:
                    # Extraction can list multimodal models which are not
                    # supported by the chat. Only offer chat-approved models.
                    supported = {model_id for _, model_id in coach_model_choices()}
                    options = [
                        (label, model_id)
                        for label, model_id in get_free_inbody_models()
                        if model_id in supported
                    ]
                    if not options:
                        raise ValueError("No hay modelos Gemini Flash para el chat.")
                    ids = {model_id for _, model_id in options}
                    selected = (
                        selected_model if selected_model in ids else
                        default_coach_model()
                    )
                    if selected not in ids:
                        selected = options[0][1]
                    return gr.update(choices=options, value=selected)
                except Exception as exc:
                    popup_error(exc, "No se pudieron consultar los modelos Gemini.")
                    return gr.update()

            def enqueue_coach_message(question, messages, model):
                try:
                    updated, pending = enqueue_user_message(question, messages)
                    if model not in {item[1] for item in coach_model_choices()}:
                        raise ValueError("Selecciona un modelo Gemini válido.")
                except ValueError as exc:
                    raise ValueError(str(exc)) from None
                # Display the user's new message immediately and a temporary
                # typing bubble. Only confirmed turns are stored in State.
                typing = updated + [{"role": "assistant", "content": "Escribiendo…"}]
                return (
                    updated, typing, pending, model,
                    gr.update(value="", interactive=False),
                    gr.update(interactive=False),
                    gr.update(interactive=False),
                    gr.update(interactive=False),
                    gr.update(interactive=False),
                )

            def complete_coach_message(
                messages, pending, report_id, goals, restrictions, days,
                model, consent,
                profile: gr.OAuthProfile | None = None,
                request: gr.Request | None = None,
            ):
                try:
                    if not pending or not messages or messages[-1]["role"] != "user":
                        raise ValueError("No hay una pregunta pendiente.")
                    conversation, context, _ = answer_coach_question(
                        pending, messages[:-1], report_id, goals, restrictions,
                        days, model, consent, profile=profile, request=request,
                    )
                    reply = conversation[-1]["content"]
                    updated = append_assistant_message(messages, reply)
                    counts = context["training"]
                    metrics = context["inbody"]
                    status = (
                        f"**Fuentes:** {counts['sets_recorded']} series del gym "
                        f"en {counts['days_recorded']} días; "
                        f"{metrics['distinct_series']} series InBody "
                        f"en {days} días. {context['inbody_source_status']} "
                        "Conversación conservada solo durante esta sesión."
                    )
                except Exception as exc:
                    # Never lose the user's question on a failed model call.
                    # Give one useful chat-level error rather than silently
                    # reverting the interface with keep_components().
                    detail = (
                        str(exc)[:350] if isinstance(exc, (ValueError, PermissionError))
                        else "Servicio temporalmente no disponible."
                    )
                    updated = append_assistant_message(
                        messages, "No pude responder esta vez. "
                        + detail + " Puedes volver a preguntarme.",
                    )
                    status = "No se completó la consulta. El mensaje sigue en el chat."
                return (
                    updated, updated, status, "", "",
                    gr.update(interactive=True),
                    gr.update(interactive=True),
                    gr.update(interactive=True),
                    gr.update(interactive=True),
                    gr.update(interactive=True),
                )

            coach_refresh_models.click(
                fn=coach_refresh_model_options,
                inputs=[coach_model], outputs=[coach_model],
                concurrency_limit=1,
            )
            # One shared trigger handles both Enter and Enviar. The first
            # callback paints bubbles BEFORE the slow Gemini request.
            gr.on(
                triggers=[coach_send.click, coach_question.submit],
                fn=enqueue_coach_message,
                inputs=[coach_question, coach_history, coach_model],
                outputs=[
                    coach_history, coach_chat, coach_pending_question,
                    coach_pending_model, coach_question, coach_send, coach_clear,
                    coach_model, coach_refresh_models,
                ],
                trigger_mode="once",
                concurrency_limit=1,
                concurrency_id="hj-fitness-chat-turn",
                api_name=False,
            ).success(
                fn=complete_coach_message,
                inputs=[
                    coach_history, coach_pending_question, coach_report_id,
                    coach_goals, coach_restrictions, coach_window,
                    coach_pending_model, session_coach_consent,
                ],
                outputs=[
                    coach_history, coach_chat, coach_context_status,
                    coach_pending_question, coach_pending_model,
                    coach_question, coach_send, coach_clear,
                    coach_model, coach_refresh_models,
                ],
                concurrency_limit=1,
                concurrency_id="hj-fitness-chat-turn",
                api_name=False,
            )
            coach_clear.click(
                fn=lambda: ([], [], "Conversación limpiada.", "", "", ""),
                outputs=[
                    coach_history, coach_chat, coach_context_status,
                    coach_pending_question, coach_pending_model, coach_question,
                ],
                queue=False,
                api_name=False,
            )
    nav_buttons = [nav_project, nav_inbody, nav_training, nav_coach]
    module_panels = [project_panel, inbody_panel, training_panel, coach_panel]
    def switch_module(section):
        if section not in dict(NAV_SECTIONS):
            raise ValueError("Módulo no válido.")
        return (
            gr.update(visible=(section == "inbody")),
            *(gr.update(visible=(key == section)) for key, _ in NAV_SECTIONS),
            *(gr.update(variant="primary" if key == section else "secondary")
              for key, _ in NAV_SECTIONS),
        )
    # Keep the four panels mounted while switching: no horizontal tabs or ellipsis.
    for key, button in zip((item[0] for item in NAV_SECTIONS), nav_buttons):
        button.click(
            fn=lambda key=key: switch_module(key),
            outputs=[inbody_navbar, *module_panels, *nav_buttons],
            show_progress="hidden", queue=False, api_name=False,
        )

    # Populate the selector once per page load and let users refresh manually.
    # Never send the uploaded report during model discovery.
    demo.load(
        fn=check_models_with_popup,
        outputs=[gemini_model_selector, gemini_models_status],
        show_progress="hidden",
    )
    # Choices were explicitly submitted before login. Restore them in both
    # tabs and keep subsequent changes server-side until logout.
    demo.load(
        fn=restore_session_consents,
        outputs=[session_ai_consent, session_db_consent, session_coach_consent],
        show_progress="hidden",
        api_name=False,
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1",
        server_port=int(os.environ.get("PORT", "7860")),
        share=False,
        ssr_mode=False,
        css=INBODY_FLOW_CSS + SIDEBAR_CSS + COACH_CHAT_CSS + SINGLE_ERROR_MESSAGE_CSS,
        show_error=False,
        auth=authenticate_master_demo if password_login_enabled() else None,
        auth_message=LOGIN_AUTH_MESSAGE if password_login_enabled() else None,
        app_kwargs={
            "routes": [
                Route("/privacy", privacy_page, methods=["GET"]),
                Route("/privacy/consent", submit_consent, methods=["POST"]),
                Route("/privacy/verify", verify_consent_session, methods=["GET"]),
            ],
            "middleware": [Middleware(PrivacyFirstMiddleware)],
        },
    )
