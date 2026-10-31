"""Health Journey: Gradio + Pydantic for InBody upload, review and CSV drafts.

Runs inside the existing Gradio/ZeroGPU Space. No database or user authentication:
use only synthetic or anonymized InBody reports during QA.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import spaces  # ZeroGPU compatibility: import before torch.
import torch
import easyocr
import gradio as gr
import numpy as np
import pandas as pd

from inbody_mvp.extractor import (
    DocumentError, MAX_UPLOAD_BYTES, extract_document,
)
from inbody_mvp.review import REVIEW_COLUMNS, export_draft_csv, review_table
from inbody_mvp.storage import (
    database_enabled, prepare_confirmed_exam, save_confirmed_exam,
    DuplicateExam,
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


# Keep the existing reader initialization model to preserve ZeroGPU behavior.
DEVICE = "cuda" if os.environ.get("SPACE_ID") or torch.cuda.is_available() else "cpu"
reader = easyocr.Reader(["es", "en"], gpu=DEVICE, verbose=False)


def _ocr_picture(image) -> str:
    # Return bounding boxes so the extractor can associate labels with
    # their cells in dense, multi-column InBody reports.
    return reader.readtext(
        np.asarray(image.convert("RGB")), detail=1, paragraph=False,
    )


@spaces.GPU
def process_report(file_path: str | None):
    """Process one upload with a GPU OCR fallback (also runs on local CPU)."""
    if not file_path:
        raise gr.Error("Carga un PDF, JPG, JPEG o PNG.")
    path = Path(file_path)
    try:
        if not path.is_file() or path.stat().st_size > MAX_UPLOAD_BYTES:
            raise DocumentError("Archivo inexistente o mayor de 15 MB.")
        result = extract_document(path.name, path.read_bytes(), ocr=_ocr_picture)
    except (DocumentError, OSError) as exc:
        raise gr.Error(f"No se pudo procesar el reporte: {exc}") from exc
    except Exception as exc:
        # Do not expose document contents, traceback or identifying data to a public UI.
        raise gr.Error(f"Falló la extracción ({type(exc).__name__}).") from exc
    status = (
        f"**Archivo:** {path.name} · **Mediciones candidatas:** {len(result.medidas)} · "
        f"**Páginas:** {len(result.texto_por_pagina)} · **Estado:** pendiente de revisión."
    )
    return (
        status,
        result.id_persona or "",
        result.modelo_inbody or "",
        result.timestamp or "",
        result.edad,
        f"Origen de la edad: {result.origen_edad or 'desconocido'}",
        result.idioma_reporte,
        review_table(result),
        "\n\n--- Página siguiente ---\n\n".join(result.texto_por_pagina),
        "\n".join(f"• {item}" for item in result.advertencias) or "Sin advertencias adicionales.",
        result.model_dump(mode="json"),
    )


def download_draft(table, person, model, timestamp, age):
    try:
        frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table, columns=REVIEW_COLUMNS)
        content = export_draft_csv(frame, person, model, timestamp, age)
    except (ValueError, TypeError) as exc:
        raise gr.Error(str(exc)) from exc
    # Gradio handles file transfer via its temporary cache, which is cleaned periodically.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", prefix="inbody_borrador_", delete=False, encoding="utf-8-sig", newline="") as file:
        file.write(content)
        return file.name


with gr.Blocks(title="Health Journey", analytics_enabled=False, delete_cache=(60, 60)) as demo:
    gr.Markdown("# Health Journey · InBody Hub")
    with gr.Tab("InBody Upload"):
        gr.Markdown(
            "**MVP de extracción y revisión** — admite PDF, JPG, JPEG y PNG (máximo 15 MB). "
            "Usa **únicamente archivos sintéticos o anonimizados**: este QA público "
            "todavía no tiene autenticación ni persistencia segura."
        )
        upload = gr.File(label="Reporte InBody", file_types=[".pdf", ".jpg", ".jpeg", ".png"], type="filepath")
        extract_button = gr.Button("Extraer mediciones", variant="primary")
        status = gr.Markdown("Sube un archivo y pulsa «Extraer mediciones».")
        with gr.Row():
            person = gr.Textbox(label="Cédula / ID indicado en el reporte")
            model = gr.Textbox(label="Modelo InBody o identificador del equipo")
        with gr.Row():
            timestamp = gr.Textbox(label="Timestamp del examen (ISO 8601 si se conoce)")
            age = gr.Number(label="Edad al realizarse el examen", precision=0)
        age_source = gr.Markdown("Origen de la edad: desconocido")
        report_language = gr.Dropdown(
            choices=["ES", "EN", "UNKNOWN"], value="UNKNOWN",
            label="Idioma del reporte (confirmar)",
            info="ES = español; EN = inglés; UNKNOWN = no reconocido",
        )
        extraction_state = gr.State(value=None)
        gr.Markdown("### Mediciones candidatas (editar antes de exportar)")
        table = gr.Dataframe(
            headers=REVIEW_COLUMNS,
            datatype=["str", "str", "str", "str", "str", "number", "str", "number", "number", "str"],
            type="pandas", interactive=True, static_columns=[0, 8, 9],
            label="Una fila por medición; valores sin confirmar",
        )
        gr.Markdown("Los valores, unidades, segmentos y frecuencias deben cotejarse con el documento original.")
        with gr.Accordion("Advertencias y texto extraído", open=False):
            warnings = gr.Textbox(label="Advertencias", lines=5, interactive=False)
            raw = gr.Textbox(label="Texto OCR / PDF", lines=12, interactive=False)
        export_button = gr.Button("Exportar borrador CSV (no guarda en una base de datos)")
        csv_file = gr.File(label="CSV borrador", interactive=False)
        extract_button.click(
            fn=process_report, inputs=[upload],
            outputs=[status, person, model, timestamp, age, age_source, report_language,
                     table, raw, warnings, extraction_state],
            concurrency_limit=1,
        )
        export_button.click(
            fn=download_draft,
            inputs=[table, person, model, timestamp, age],
            outputs=[csv_file],
        )
        if database_enabled():
            gr.Markdown(
                "### Guardar examen confirmado en Neon (solo sesión local privada)\n"
                "Verifica identificación, idioma, valores, unidades y fecha antes de continuar."
            )
            save_button = gr.Button("Confirmar y guardar en PostgreSQL", variant="primary")
            saved_status = gr.Markdown()
            def save_reviewed(state, edited, person_id, device, when, years, lang):
                if state is None:
                    raise gr.Error("Primero procesa un reporte.")
                try:
                    payload = prepare_confirmed_exam(
                        state, edited, person_id, device, when, years, lang
                    )
                    exam_id = save_confirmed_exam(payload)
                except (ValueError, TypeError, RuntimeError) as exc:
                    raise gr.Error(str(exc)) from exc
                return f"Examen confirmado y guardado. ID interno: `{exam_id}`."
            save_button.click(
                fn=save_reviewed,
                inputs=[extraction_state, table, person, model, timestamp, age, report_language],
                outputs=[saved_status],
                concurrency_limit=1,
            )
        else:
            gr.Markdown(
                "**Persistencia Neon deshabilitada en este entorno.** "
                "El Space público solo permite revisar y exportar borradores. "
                "Para guardar, configura DATABASE_URL y ENABLE_PERSISTENCE=1 "
                "en una ejecución local privada."
            )
        gr.ClearButton([upload, status, person, model, timestamp, age, age_source,
                        report_language, table, raw, warnings, csv_file, extraction_state],
                       value="Limpiar")
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
    demo.launch(server_name="127.0.0.1" if database_enabled() else "0.0.0.0", server_port=int(os.environ.get("PORT", "7860")), share=False, ssr_mode=False)
