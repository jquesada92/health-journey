"""Gemini structured extraction, human review and immutable per-measurement audit."""
from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf as fitz
import pandas as pd
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .extractor import MAX_UPLOAD_BYTES
from .prompt_loader import load_prompt

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

# Official Google Developer API pricing (Nov 2026) documents a standard
# free tier for these multimodal Flash models. Availability and actual
# billing are per API key/project; a paid-tier project can still be billed.
# Never display arbitrary models.list results as if they were free.
FREE_INBODY_FLASH_MODELS = {
    "gemini-3.8-flash": "Gemini 3.8 Flash · recomendado para tablas complejas",
    "gemini-3.6-flash": "Gemini 3.6 Flash · multimodal",
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite · rápido",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite · ligero",
    "gemini-2.5-flash": "Gemini 2.5 Flash · acceso restringido en algunos proyectos",
    "gemini-2.5-flash-lite": "Gemini 2.5 Flash-Lite · acceso restringido",
}


COLUMNS = ["exam_datetime", "filename", "person_id", "age", "section",
           "measurement", "value", "unit", "original_value", "was_corrected",
           "correction_comment", "reviewed"]
# UI displays per-exam metadata only once above the measurement table.
# Keep full COLUMNS as the backend interchange contract for existing clients.
DISPLAY_COLUMNS = [name for name in COLUMNS
                   if name not in ("exam_datetime", "filename", "person_id", "age")]
PROMPT = load_prompt("inbody_extraction")
class Header(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: str | None = Field(description="Person ID exactly as printed; preserve leading zeros")
    exam_datetime: str | None = Field(description="Exam header timestamp, YYYY-MM-DD HH:MM:SS")
    age: int | None = Field(description="Age printed in exam header, null when absent")

class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str
    measurement: str
    value: str = Field(description="Numeric measurement as exact printed text, including trailing zeros")
    unit: str | None

class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    header: Header
    measurements: list[Measurement]
    missing_or_unreadable: list[str]

def _pages(name: str, data: bytes) -> list[Image.Image]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("El archivo excede el límite de carga.")
    if Path(name).suffix.lower() == ".pdf":
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if len(pdf) > 10:
                raise ValueError("Máximo 10 páginas por archivo.")
            return [Image.open(io.BytesIO(p.get_pixmap(matrix=fitz.Matrix(1.6, 1.6)).tobytes("png"))).convert("RGB") for p in pdf]
    if Path(name).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("Formato no permitido.")
    image = Image.open(io.BytesIO(data))
    image.verify()
    return [Image.open(io.BytesIO(data)).convert("RGB")]

def render_document_preview(upload_state):
    """Render a local, read-only PDF/image page viewer before Gemini consent.

    Reuses the same validated pages as extraction. No external API call and
    no modification of the original report. Only anonymized files should be
    uploaded to a public Space, since Gradio caches images for the browser.
    """
    if not upload_state:
        return [], "Carga un PDF o imagen para visualizarlo."
    try:
        name = upload_state["filename"]
        pages = _pages(name, upload_state["data"])
        if not pages:
            raise ValueError("El documento no contiene páginas visibles.")
        images = [(page, f"Página {i}") for i, page in enumerate(pages, start=1)]
        return images, f"{len(images)} página(s). Selecciona una página y amplíala para comparar los resultados."
    except Exception as exc:
        raise _ui_error(f"No se pudo visualizar el documento ({type(exc).__name__}).") from None


def _ui_error(message: str):
    # Gradio is a UI-only dependency; unit tests can import this module without it.
    try:
        import gradio as gr
    except ImportError:
        return ValueError(message)
    return gr.Error(message)


def gemini_api_error_message(code: int | None) -> str:
    """Provide actionable HTTP diagnostics without exposing remote error payloads.

    Google error messages can contain request details, so never display
    exception.message, exception.details, API keys or document content.
    """
    try:
        http_code = int(code) if code is not None else 0
    except (ValueError, TypeError):
        http_code = 0
    advice = {
        400: "Solicitud rechazada. Comprueba el modelo y la compatibilidad del esquema JSON.",
        401: "Credenciales no autorizadas. Comprueba GEMINI_API_KEY en los secretos de Hugging Face.",
        403: "Acceso denegado. Comprueba permisos, restricciones de la clave y disponibilidad regional.",
        404: "Modelo no encontrado o no accesible. Revisa GEMINI_MODEL y los modelos habilitados.",
        413: "Documento demasiado grande para la API. Prueba una imagen o PDF más pequeño.",
        429: "Cuota o límite de solicitudes alcanzado. Revisa los límites en Google AI Studio.",
        500: "Error interno temporal de la API de Gemini. Reintenta más adelante.",
        502: "Error temporal de comunicación con Gemini. Reintenta más adelante.",
        503: "Servicio Gemini temporalmente no disponible. Reintenta más adelante.",
        504: "Gemini agotó el tiempo de respuesta. Prueba menos páginas.",
    }.get(http_code, "La API rechazó o no pudo completar la solicitud. Revisa el servicio y su configuración.")
    code_label = f"HTTP {http_code}" if http_code else "HTTP desconocido"
    return f"Gemini ({code_label}): {advice}"


def _model_name() -> str:
    """Choose the current Flash model unless the Space specifies another."""
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL


def available_flash_models(client) -> list[str]:
    """List Flash text-generation models available to this API key.

    Never expose secrets or raw API responses; model IDs are public metadata.
    """
    available = set()
    for item in client.models.list():
        model_name = (getattr(item, "name", "") or "").removeprefix("models/")
        actions = getattr(item, "supported_actions", None) or []
        if (
            model_name.startswith("gemini-")
            and ("-flash" in model_name)
            and not any(x in model_name for x in ("-image", "-live", "-tts", "-audio"))
            and "generateContent" in actions
        ):
            available.add(model_name)
    return sorted(available)


def free_model_options(available_names: list[str]) -> list[tuple[str, str]]:
    """Intersection of Google documented Free Tier and the API-key model list.

    Model listing does not reveal whether a project is billed or its remaining
    free quota. Labels must not claim zero charges are guaranteed.
    """
    available = set(available_names)
    return [
        (label + " · Free Tier", model_id)
        for model_id, label in FREE_INBODY_FLASH_MODELS.items()
        if model_id in available
    ]


def get_free_inbody_models() -> list[tuple[str, str]]:
    """Query server-side model metadata, never upload images or expose keys."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Configura GEMINI_API_KEY en los Secrets del Space.")
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        result = free_model_options(available_flash_models(client))
    except Exception as exc:
        kind = type(exc)
        if kind.__module__.startswith("google.genai"):
            raise ValueError(gemini_api_error_message(getattr(exc, "code", None))) from None
        raise ValueError("No se pudieron consultar los modelos de Gemini.") from None
    if not result:
        raise ValueError(
            "Tu API key no devolvió modelos Flash compatibles con Free Tier. "
            "Revisa permisos y cuotas en Google AI Studio."
        )
    return result


def check_gemini_models() -> str:
    """Diagnostic only: lists accessible models; sends NO InBody document."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Falta GEMINI_API_KEY en los secretos del Space."
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        compatible = available_flash_models(client)
    except Exception as exc:
        # Do not print raw provider errors (may contain request details).
        kind = type(exc)
        code = getattr(exc, "code", None)
        if kind.__module__.startswith("google.genai"):
            return gemini_api_error_message(code)
        return f"No fue posible consultar los modelos ({kind.__name__})."
    current = _model_name()
    if not compatible:
        return "La API key no devolvió ningún modelo Flash con soporte generateContent."
    lines = chr(10).join(f"- `{name}`" for name in compatible)
    status = "Disponible" if current in compatible else "No aparece en la lista"
    return f"Modelo configurado: `{current}` ({status})." + chr(10) + "Modelos Flash accesibles:" + chr(10) + lines


def _fallback_model(primary_model: str) -> str | None:
    """One alternate model only; disable with GEMINI_FALLBACK_MODEL=off."""
    configured = os.getenv("GEMINI_FALLBACK_MODEL")
    candidate = (
        DEFAULT_GEMINI_FALLBACK_MODEL if configured is None
        else configured.strip()
    )
    if (
        candidate.lower() in ("", "off", "disabled", "none")
        or candidate == primary_model
        or candidate not in FREE_INBODY_FLASH_MODELS
    ):
        return None
    return candidate


def _is_gemini_overloaded(exc: Exception) -> bool:
    """Do not retry malformed requests, 429 rate limits or auth errors."""
    kind = type(exc)
    return (
        kind.__module__.startswith("google.genai")
        and kind.__name__ in ("ClientError", "ServerError")
        and getattr(exc, "code", None) == 503
    )


def extract_gemini(upload_state, consent=False, selected_model=None):
    if not upload_state:
        raise _ui_error("Primero carga un documento.")
    if consent is not True:
        raise _ui_error("Debes autorizar explícitamente el envío de este documento a Gemini.")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise _ui_error("Falta GEMINI_API_KEY en los secretos del Space.")
    client = None
    selected_model = str(selected_model or _model_name()).strip()
    if selected_model not in FREE_INBODY_FLASH_MODELS:
        raise _ui_error(
            "Selecciona un modelo Gemini Flash con Free Tier documentado."
        )
    active_model = selected_model
    failover_used = False
    try:
        from google import genai
        from google.genai import types
        name, data = upload_state["filename"], upload_state["data"]
        pages = _pages(name, data)
        client = genai.Client(api_key=api_key)
        # The official Gemini SDK already retries transient errors with
        # exponential backoff. Do not add another retry loop to the same model.
        # After its retries exhaust, attempt ONE alternate model on HTTP 503.
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=Extraction.model_json_schema(),
            # Gemini 3.6+ models ignore explicit temperature values.
        )
        try:
            response = client.models.generate_content(
                model=selected_model,
                contents=[PROMPT, *pages],
                config=generation_config,
            )
        except Exception as primary_exc:
            alternate = _fallback_model(selected_model)
            if not alternate or not _is_gemini_overloaded(primary_exc):
                raise
            active_model = alternate
            # Only one alternate request after SDK's own retry handling.
            response = client.models.generate_content(
                model=alternate,
                contents=[PROMPT, *pages],
                config=generation_config,
            )
            failover_used = True
        result = Extraction.model_validate_json(response.text)
        if not result.header.exam_datetime or not result.header.person_id:
            raise ValueError("No se identificó el ID o la fecha/hora del encabezado.")
        datetime.fromisoformat(result.header.exam_datetime)
        rows = []
        for m in result.measurements:
            rows.append({
                "exam_datetime": result.header.exam_datetime, "filename": name,
                "person_id": result.header.person_id, "age": result.header.age,
                "section": m.section, "measurement": m.measurement,
                "value": m.value, "unit": m.unit or "",
                "original_value": m.value, "was_corrected": False,
                "correction_comment": "", "reviewed": False,
            })
        snapshot = {"sha256": hashlib.sha256(data).hexdigest(),
                    "header": result.header.model_dump(),
                    "raw_response": response.text,
                    "rows": rows, "filename": name,
                    "model": active_model,
                    "primary_model": selected_model,
                    "fallback_used": failover_used}
        frame = pd.DataFrame(rows, columns=COLUMNS)
        message = f"{len(rows)} mediciones extraídas; pendientes de revisión."
        if failover_used:
            message += f" Modelo principal sin capacidad (503); extracción con {active_model}."
        if result.missing_or_unreadable:
            message += " Campos ilegibles: " + ", ".join(result.missing_or_unreadable)
        return frame, snapshot, message
    except Exception as exc:
        # Identify errors from the SDK without importing it at module load.
        # This also handles a missing SDK dependency cleanly.
        kind = type(exc)
        if kind.__module__.startswith("google.genai") and kind.__name__ in (
            "ClientError", "ServerError"
        ):
            code = getattr(exc, "code", None)
            message = gemini_api_error_message(code)
            if code == 404 and client is not None:
                try:
                    accessible = available_flash_models(client)
                    message += f" Modelo solicitado: {active_model}."
                    if accessible:
                        message += " Flash accesibles para tu API key: " + ", ".join(accessible[:12]) + "."
                    else:
                        message += " No se encontraron modelos Flash disponibles para tu API key."
                except Exception:
                    message += " Usa 'Comprobar modelos' para verificar tu API key."
            # Avoid surfacing raw request errors, which may include private data.
            raise _ui_error(message) from None
        raise _ui_error(f"No se pudo extraer el reporte ({type(exc).__name__}).") from None

def _string(value):
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()

def _decimal(value):
    raw = _string(value)
    if not raw:
        raise ValueError("Medición sin valor.")
    try:
        number = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Valor numérico inválido.") from exc
    if not number.is_finite():
        raise ValueError("Valor no finito.")
    return number

def _mutation_review_grid(table, snapshot):
    """Require the original immutable AI values before editing or deleting.

    The review grid can contain malformed numeric values because those are
    exactly what the user needs to repair. Only the provenance column and
    number of rows are checked here, not the numeric values.
    """
    if not snapshot or not isinstance(snapshot.get("rows"), list):
        raise ValueError("Primero extrae un examen InBody.")
    frame = table.copy() if isinstance(table, pd.DataFrame) else pd.DataFrame(
        table, columns=DISPLAY_COLUMNS
    )
    if len(frame) != len(snapshot["rows"]):
        raise ValueError(
            "La tabla no coincide con el examen. Usa el botón Eliminar fila "
            "seleccionada en lugar de borrar filas directamente de la cuadrícula."
        )
    if "original_value" not in frame.columns:
        raise ValueError("Falta el valor original de las mediciones.")
    for index, (row, original) in enumerate(
        zip(frame.to_dict("records"), snapshot["rows"]), start=1
    ):
        for key in ("exam_datetime", "filename", "person_id", "age"):
            if key in row and _string(row.get(key)) != _string(original.get(key)):
                raise ValueError(
                    f"Fila {index}: no se permiten cambios en datos originales."
                )
        if _string(row.get("original_value")) != _string(original["original_value"]):
            raise ValueError(
                f"Fila {index}: no se permiten cambios en datos originales; " 
                "el valor original no se puede cambiar ni reordenar."
            )
    return frame.reindex(columns=DISPLAY_COLUMNS).reset_index(drop=True)


def remove_review_row(table, snapshot, row_index):
    """Remove one reviewed candidate without changing the raw AI evidence.

    The session snapshot's retained rows stay aligned with the visual grid.
    The unmodified raw_response still records every original AI candidate.
    """
    frame = _mutation_review_grid(table, snapshot)
    if not isinstance(row_index, int) or isinstance(row_index, bool):
        raise ValueError("Selecciona una fila válida.")
    if not 0 <= row_index < len(frame):
        raise ValueError("La fila seleccionada ya no existe.")
    if len(frame) <= 1:
        raise ValueError("Debes conservar al menos una medición para revisar.")
    from copy import deepcopy

    new_snapshot = deepcopy(snapshot)
    removed = new_snapshot["rows"].pop(row_index)
    new_snapshot.setdefault("excluded_review_rows", []).append({
        "measurement": removed.get("measurement"),
        "original_value": removed.get("original_value"),
    })
    updated = frame.drop(index=row_index).reset_index(drop=True)
    return updated, new_snapshot


def correct_review_value(table, snapshot, row_index, value, reason):
    """Repair an invalid Gemini value even if inline grid editing is blocked."""
    frame = _mutation_review_grid(table, snapshot)
    if not isinstance(row_index, int) or isinstance(row_index, bool):
        raise ValueError("Selecciona una fila válida.")
    if not 0 <= row_index < len(frame):
        raise ValueError("La fila seleccionada ya no existe.")
    new_value = _string(value)
    try:
        _decimal(new_value)
    except ValueError as exc:
        raise ValueError(f"Fila {row_index + 1}: {exc}") from exc
    new_reason = _string(reason)
    original = snapshot["rows"][row_index]
    needs_comment = any(
        _string(frame.iloc[row_index][key]) != _string(original.get(key))
        for key in ("section", "measurement", "unit")
    ) or new_value != _string(original.get("value"))
    if needs_comment and not new_reason:
        raise ValueError(
            f"Fila {row_index + 1}: escribe un motivo para corregir el valor."
        )
    if len(new_reason) > 1200:
        raise ValueError("El comentario supera 1200 caracteres.")
    frame.at[row_index, "value"] = new_value
    frame.at[row_index, "correction_comment"] = new_reason
    frame.at[row_index, "was_corrected"] = bool(needs_comment)
    # Preserve reviewed as entered by the person: do not autoapprove a row.
    return frame


def sync_review_corrections(table, snapshot):
    """Reconcile inline edits with original AI values without autoapproving.

    Numeric strings are not coerced to float: '-0.370' and '8.20' retain
    their literal precision. A changed value (or another edited measurement
    field) always takes precedence over a manually unchecked flag. A flag
    cannot be forced True when the measurement still matches the original;
    this invariant is also enforced by the audit writer.
    """
    frame = _mutation_review_grid(table, snapshot)
    for index, original in enumerate(snapshot["rows"]):
        changed = any(
            _string(frame.at[index, key]) != _string(original.get(key))
            for key in ("value", "unit", "section", "measurement")
        )
        frame.at[index, "was_corrected"] = bool(changed)
    return frame


def reconcile_native_review_rows(table, snapshot):
    """Accept Gradio's native row deletion while preserving audit provenance.

    A dataframe edit has no stable source-row ID. Find the unique best
    order-preserving match against immutable original_value and unchanged
    source labels. If source rows are indistinguishable after edits/deletion,
    fail closed rather than attribute measurements to the wrong source.
    """
    if not snapshot or not isinstance(snapshot.get("rows"), list):
        raise ValueError("Primero extrae un examen InBody.")
    frame = table.copy() if isinstance(table, pd.DataFrame) else pd.DataFrame(
        table, columns=DISPLAY_COLUMNS
    )
    if not set(DISPLAY_COLUMNS).issubset(frame.columns):
        raise ValueError("Faltan columnas obligatorias de la revisión.")
    frame = frame.reindex(columns=DISPLAY_COLUMNS).reset_index(drop=True)
    source = snapshot["rows"]
    if len(frame) > len(source):
        raise ValueError(
            "No puedes agregar filas al examen desde la tabla. "
            "Solo corrige o elimina las mediciones extraídas."
        )
    if not len(frame):
        raise ValueError("Debes conservar al menos una medición para revisar.")
    if len(frame) == len(source):
        return sync_review_corrections(frame, snapshot), snapshot

    # Gradio's native delete event reports only the remaining grid. Original
    # readings and relative row order identify retained measurements; labels
    # are used to distinguish repeated values such as segmental 0.375.
    rows = frame.to_dict("records")
    n, m = len(rows), len(source)
    impossible = -10 ** 9
    scores = [[impossible] * (m + 1) for _ in range(n + 1)]
    counts = [[0] * (m + 1) for _ in range(n + 1)]
    decisions = [[None] * m for _ in range(n)]
    for j in range(m + 1):
        scores[n][j], counts[n][j] = 0, 1

    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            # Option A: this source measurement was deleted.
            best, possibilities, choice = scores[i][j + 1], counts[i][j + 1], "skip"
            candidate = source[j]
            if _string(rows[i].get("original_value")) == _string(
                candidate.get("original_value")
            ) and counts[i + 1][j + 1]:
                # Value is immutable. Labels can be edited during human
                # review, so we score hints rather than require equality.
                match_score = (
                    16 * (_string(rows[i].get("measurement")) == _string(
                        candidate.get("measurement")
                    ))
                    + 8 * (_string(rows[i].get("section")) == _string(
                        candidate.get("section")
                    ))
                    + 4 * (_string(rows[i].get("unit")) == _string(
                        candidate.get("unit")
                    ))
                    + (_string(rows[i].get("value")) == _string(
                        candidate.get("value")
                    ))
                ) + scores[i + 1][j + 1]
                if match_score > best:
                    best = match_score
                    possibilities = counts[i + 1][j + 1]
                    choice = "match"
                elif match_score == best:
                    possibilities = min(2, possibilities + counts[i + 1][j + 1])
            scores[i][j], counts[i][j], decisions[i][j] = best, possibilities, choice

    if not counts[0][0]:
        raise ValueError(
            "No se pueden relacionar las filas restantes con sus valores "
            "originales. Comprueba que original_value no haya cambiado."
        )
    if counts[0][0] > 1:
        raise ValueError(
            "Hay varias filas originales indistinguibles después del borrado. "
            "No se puede determinar qué medición se eliminó sin arriesgar "
            "su auditoría; vuelve a cargar el reporte y revisa esas filas."
        )

    retained = []
    i = j = 0
    while i < n and j < m:
        if decisions[i][j] == "match":
            retained.append(j)
            i += 1
        j += 1
    if len(retained) != n:
        raise ValueError("No fue posible identificar las filas conservadas.")

    # Reuse the same provenance checks after reducing the immutable snapshot.
    from copy import deepcopy

    updated_snapshot = deepcopy(snapshot)
    keep = set(retained)
    updated_snapshot["rows"] = [source[index] for index in retained]
    updated_snapshot.setdefault("excluded_review_rows", []).extend(
        {
            "measurement": original.get("measurement"),
            "original_value": original.get("original_value"),
        }
        for index, original in enumerate(source) if index not in keep
    )
    return sync_review_corrections(frame, updated_snapshot), updated_snapshot


def compact_review_table(table):
    """Hide repeated exam metadata from the editable measurements grid."""
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table, columns=COLUMNS)
    return frame.reindex(columns=DISPLAY_COLUMNS).copy()


def header_for_review(snapshot):
    """Return one editable exam header, plus a blank correction reason.

    Filename remains read-only: it is original file provenance, not a metric.
    """
    if not snapshot:
        return ("", "", "", "", "")
    original = snapshot.get("header") or snapshot["rows"][0]
    return (
        _string(original.get("exam_datetime")),
        _string(snapshot.get("filename") or snapshot["rows"][0].get("filename")),
        _string(original.get("person_id")),
        _string(original.get("age")),
        "",
    )


def _effective_header(snapshot, header_edits):
    """Validate a single correction and apply it to every exported record.

    The original extraction is never rewritten; snapshot.raw_response remains
    the AI evidence. A header correction requires only ONE UI comment.
    """
    base = (snapshot.get("header") or snapshot["rows"][0])
    old = {
        "exam_datetime": _string(base.get("exam_datetime")),
        "person_id": _string(base.get("person_id")),
        "age": base.get("age"),
        "filename": _string(snapshot.get("filename") or snapshot["rows"][0]["filename"]),
    }
    if header_edits is None:
        return old, False, ""
    if not isinstance(header_edits, dict):
        raise ValueError("Encabezado inválido.")
    if _string(header_edits.get("filename")) != old["filename"]:
        raise ValueError("El nombre original del archivo no puede modificarse.")
    timestamp = _string(header_edits.get("exam_datetime"))
    try:
        datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("Fecha/hora inválida: usa YYYY-MM-DD HH:MM:SS.") from exc
    person = _string(header_edits.get("person_id"))
    if not person or len(person) > 80:
        raise ValueError("El ID de persona es obligatorio (máximo 80 caracteres).")
    age_value = _string(header_edits.get("age"))
    if age_value:
        try:
            age = int(age_value)
        except ValueError as exc:
            raise ValueError("La edad debe ser un número entero.") from exc
        if not 0 <= age <= 120:
            raise ValueError("La edad debe estar entre 0 y 120 años.")
    else:
        age = None
    effective = dict(old, exam_datetime=timestamp, person_id=person, age=age)
    changed = any(
        _string(effective[k]) != _string(old[k])
        for k in ("exam_datetime", "person_id", "age")
    )
    comment = _string(header_edits.get("correction_comment"))
    if changed and not comment:
        raise ValueError("Describe una sola vez el motivo de la corrección del encabezado.")
    if len(comment) > 1200:
        raise ValueError("El comentario de encabezado supera 1200 caracteres.")
    return effective, changed, comment


def validate_review(table, snapshot, header_edits=None):
    if not snapshot:
        raise ValueError("Primero extrae un documento.")
    frame = sync_review_corrections(table, snapshot)
    original = snapshot["rows"]
    header, header_changed, header_reason = _effective_header(snapshot, header_edits)
    verified = []
    for i, (row, base) in enumerate(zip(frame.to_dict("records"), original), start=1):
        # Legacy full-width callers cannot forge original headers or AI values.
        for key in ("exam_datetime", "filename", "person_id", "age", "original_value"):
            if key in row and _string(row.get(key)) != _string(base.get(key)):
                raise ValueError(f"Fila {i}: no se permiten cambios en datos originales.")
        if not _string(row.get("section")) or not _string(row.get("measurement")):
            raise ValueError(f"Fila {i}: sección y medición obligatorias.")
        try:
            _decimal(row.get("value"))
        except ValueError as exc:
            raise ValueError(
                f"Fila {i} ({_string(row.get('measurement'))[:60]}): {exc}"
            ) from exc
        measurement_changed = any(_string(row.get(k)) != _string(base.get(k))
                                  for k in ("value", "unit", "section", "measurement"))
        comment = _string(row.get("correction_comment"))
        if measurement_changed and not comment:
            raise ValueError(f"Fila {i}: describe la corrección en el comentario.")
        reviewed = row.get("reviewed") is True or str(row.get("reviewed")).lower() == "true"
        if not reviewed:
            raise ValueError(f"Fila {i}: marca revisado antes de guardar.")
        # The change is entered once in the UI, then propagated as a
        # comment across measurements. Keep was_corrected tied ONLY to
        # measurement changes: the database validates that invariant.
        note = ("Corrección de encabezado: " + header_reason) if header_changed else ""
        combined_comment = "; ".join(part for part in (comment, note) if part)
        verified.append({
            "row_number": i,
            "exam_datetime": header["exam_datetime"], "filename": header["filename"],
            "person_id": header["person_id"], "age": header["age"],
            "section": _string(row["section"]),
            "measurement": _string(row["measurement"]),
            "value": _string(row["value"]), "unit": _string(row.get("unit")) or None,
            "original_value": base["original_value"], "original_section": base["section"],
            "original_measurement": base["measurement"], "original_unit": base["unit"],
            "was_corrected": measurement_changed,
            "correction_comment": combined_comment or None,
        })
    if not verified:
        raise ValueError("No hay mediciones para guardar.")
    return verified


def review_status(table, snapshot, header_edits=None):
    try:
        rows = validate_review(table, snapshot, header_edits)
        header_changed = bool(header_edits is not None and
                              _effective_header(snapshot, header_edits)[1])
        measurement_changes = sum(
            any(_string(display_row.get(k)) != _string(base.get(k))
                for k in ("value", "unit", "section", "measurement"))
            for display_row, base in zip(
                (table if isinstance(table, pd.DataFrame)
                 else pd.DataFrame(table, columns=DISPLAY_COLUMNS)).to_dict("records"),
                snapshot["rows"],
            )
        )
        note = ", encabezado corregido" if header_changed else ""
        return (f"Revisión completa: {len(rows)} filas, "
                f"{measurement_changes} correcciones de medición{note}.")
    except ValueError as exc:
        return "Revisión pendiente: " + str(exc)


def audit_write_enabled() -> bool:
    """Never accept administrator credentials for consent-only audit writes."""
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.exc import ArgumentError
    flag = os.getenv("ENABLE_ANONYMOUS_DEMO", "").lower().strip()
    if flag not in ("1", "true", "yes"):
        return False
    url = os.getenv("DEMO_DATABASE_URL", "")
    try:
        parsed = make_url(url)
        return (parsed.drivername in ("postgresql", "postgresql+psycopg")
                and parsed.username == "health_journey_demo_writer"
                and parsed.query.get("sslmode") == "require")
    except (ValueError, TypeError, AttributeError, ArgumentError):
        return False


def _audit_write_engine():
    from sqlalchemy import create_engine

    if not audit_write_enabled():
        raise PermissionError(
            "El guardado por consentimiento no está configurado. "
            "Define DEMO_DATABASE_URL (rol health_journey_demo_writer) y "
            "ENABLE_ANONYMOUS_DEMO=1 en Hugging Face."
        )
    uri = os.environ["DEMO_DATABASE_URL"]
    if uri.startswith("postgresql://"):
        uri = "postgresql+psycopg://" + uri[len("postgresql://"):]
    return create_engine(uri, pool_pre_ping=True, pool_size=1, max_overflow=0)


def save_audit(table, snapshot, consent, confirm_overwrite=False, profile=None,
               header_edits=None):
    """Consent-based write-only submission; never grants private read access.

    The anonymous database role has EXECUTE only on a validated stored
    procedure; it cannot SELECT personal data from audit tables.
    """
    if consent is not True:
        raise _ui_error("Debes autorizar el envío de las mediciones a Neon.")
    try:
        rows = validate_review(table, snapshot, header_edits=header_edits)
        if not audit_write_enabled():
            raise PermissionError(
                "La escritura por consentimiento no está configurada. "
                "Solicita configurar DEMO_DATABASE_URL con health_journey_demo_writer "
                "y ENABLE_ANONYMOUS_DEMO=1."
            )
        body = {
            "source_sha256": snapshot["sha256"],
            "filename": snapshot["filename"],
            "person_id": rows[0]["person_id"],
            "exam_datetime": rows[0]["exam_datetime"],
            "age": rows[0]["age"],
            "model_name": snapshot["model"],
            "raw_response": json.loads(snapshot["raw_response"]),
            "measurements": rows,
        }
        engine = _audit_write_engine()
        try:
            with engine.begin() as con:
                receipt = con.execute(
                    text(
                        "SELECT public.hj_submit_reviewed_audit_receipt("
                        "CAST(:payload AS jsonb), :confirm_overwrite, false)"
                    ),
                    {
                        "payload": json.dumps(body, ensure_ascii=False),
                        "confirm_overwrite": confirm_overwrite is True,
                    },
                ).scalar_one()
            if isinstance(receipt, str):
                receipt = json.loads(receipt)
            if receipt["status"] == "filename_processed":
                return (
                    "Este archivo ya fue procesado en Neon (nombre o contenido "
                    "idéntico). No se guardaron duplicados."
                )
            if receipt["status"] == "overwrite_required":
                count = int(receipt.get("conflicts", 0))
                return (
                    f"Ya se capturaron {count} mediciones con el mismo ID de "
                    "persona, fecha y nombre de medición. Si guardas este "
                    "nuevo reporte, esos valores se **sobrescribirán en el "
                    "dashboard**, conservando la versión anterior como "
                    "auditoría. Marca 'Confirmo sobrescribir mediciones "
                    "anteriores' y vuelve a guardar."
                )
            if receipt["status"] not in ("saved", "overwritten"):
                raise RuntimeError("Invalid audit receipt status")
            if receipt["status"] == "overwritten":
                return (
                    f"Guardado en Neon: {len(rows)} mediciones. Se actualizaron "
                    f"{receipt.get('conflicts', 0)} mediciones en el dashboard; "
                    "sus versiones anteriores permanecen en auditoría."
                )
            return (
                f"Guardado en Neon: {len(rows)} mediciones; "
                f"{sum(r['was_corrected'] for r in rows)} corregidas."
            )
        finally:
            engine.dispose()
    except (ValueError, PermissionError) as exc:
        raise _ui_error(str(exc)) from None
    except Exception as exc:
        # Never log raw SQL/bind parameters, source document, person IDs or
        # credentials. Record only the SQLSTATE and exception class.
        import logging

        db_error = getattr(exc, "orig", None)
        sqlstate = getattr(db_error, "sqlstate", None) or getattr(
            db_error, "pgcode", None
        )
        logging.getLogger(__name__).warning(
            "Neon audit write failed: sqlstate=%s, class=%s",
            sqlstate or "unknown", type(exc).__name__,
        )
        messages = {
            "42883": "No se encontró la función de guardado: aplica la migración 007.",
            "42501": "La conexión DEMO_DATABASE_URL carece del permiso EXECUTE.",
            "23505": "El archivo o la medición ya existe. Verifica el estado del reporte.",
            "23514": "Una medición incumple una validación de la base de datos.",
            "22007": "La fecha del examen tiene un formato inválido.",
            "22P02": "El reporte contiene un identificador o valor inválido.",
            "P0001": "Neon rechazó un dato del examen. Revisa el identificador, "
                     "la fecha, los valores y los comentarios de corrección.",
        }
        raise _ui_error(messages.get(
            sqlstate,
            "No se pudo guardar en Neon. Consulta el código SQLSTATE en los "
            "logs del Space, sin compartir datos personales ni claves.",
        )) from None

def check_processed_filename(upload_state, profile=None, request=None):
    """Only authenticated private users may query processed file names.

    The save procedure independently checks names even for anonymous upload.
    No file content is sent to the database by this existence check.
    """
    if not upload_state:
        return "Carga un archivo para verificarlo."
    from .storage import require_database_access, _database_engine

    try:
        require_database_access(profile, request=request)
    except PermissionError:
        return (
            "Se verificará si el archivo ya fue procesado al guardarlo. "
            "Para consultarlo antes, inicia sesión con una cuenta autorizada."
        )

    name = str(upload_state.get("filename") or "")
    if not name:
        return "No se pudo leer el nombre del archivo."
    try:
        engine = _database_engine()
        try:
            with engine.connect() as conn:
                processed = conn.execute(
                    text("SELECT public.hj_audit_filename_processed(:filename)"),
                    {"filename": name},
                ).scalar_one()
            if processed:
                return (
                    "Este nombre de archivo ya fue procesado en Neon. "
                    "No es necesario extraerlo nuevamente."
                )
            return "Archivo nuevo: no existe un registro con ese nombre."
        finally:
            engine.dispose()
    except Exception:
        return (
            "La verificación anticipada no está disponible. Neon validará "
            "el nombre y las posibles coincidencias al guardar."
        )


