"""Gemini structured extraction, human review and immutable per-measurement audit."""
from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import fitz
import pandas as pd
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .extractor import MAX_UPLOAD_BYTES
from .storage import _database_engine, require_database_access

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

COLUMNS = ["exam_datetime", "filename", "person_id", "age", "section",
           "measurement", "value", "unit", "original_value", "was_corrected",
           "correction_comment", "reviewed"]
PROMPT = """Analiza el reporte InBody proporcionado visualmente. Extrae EXCLUSIVAMENTE
las mediciones del examen actual. Ignora Body Composition History, Historial de
Composición Corporal y cualquier gráfico o tabla histórica, incluso si incluye
el valor de la prueba actual. Usa el encabezado, no el nombre del archivo ni el
historial, para ID, fecha/hora y edad. Asocia visualmente etiquetas encima de
valores, etiquetas a la izquierda de valores, celdas y segmentos corporales.
No confundas rangos, escalas o metas con resultados.
Devuelve todas las mediciones numéricas legibles: composición corporal,
músculo-grasa, obesidad, segmentales, agua, ángulo de fase, impedancia,
control de peso, investigación y Puntaje InBody. El puntaje tiene sección
'Puntaje InBody', medición 'Puntaje InBody' y unidad 'puntos'.
Cada medición tiene section, measurement, value y unit. Section es solo la
sección, sin segmento; measurement contiene el segmento cuando corresponda,
por ejemplo 'Brazo derecho - Masa magra' o 'Brazo derecho - Frecuencia'.
Representa frecuencias mostradas como filas independientes con unidad kHz;
para impedancia conserva la frecuencia en el nombre, por ejemplo
'Brazo derecho - Impedancia a 50 kHz'. Evita duplicados indistinguibles.
Preserva todos los decimales impresos EXACTAMENTE como texto: 8.20
debe seguir siendo '8.20'. No estimes ni calcules valores ausentes.
No inventes mediciones o campos ilegibles. Devuelve campos ilegibles
en missing_or_unreadable. La fecha va en YYYY-MM-DD HH:MM:SS.
Devuelve solo JSON con header, measurements y missing_or_unreadable."""

class Header(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: str | None = Field(description="ID literal con ceros iniciales")
    exam_datetime: str | None = Field(description="YYYY-MM-DD HH:MM:SS, fecha del encabezado")
    age: int | None = Field(description="Edad indicada en examen; null si no aparece")

class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str
    measurement: str
    value: str = Field(description="Decimal original en texto, incluyendo ceros")
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


def extract_gemini(upload_state, consent=False):
    if not upload_state:
        raise _ui_error("Primero carga un documento.")
    if consent is not True:
        raise _ui_error("Debes autorizar explícitamente el envío de este documento a Gemini.")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise _ui_error("Falta GEMINI_API_KEY en los secretos del Space.")
    client = None
    selected_model = _model_name()
    try:
        from google import genai
        from google.genai import types
        name, data = upload_state["filename"], upload_state["data"]
        pages = _pages(name, data)
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=selected_model,
            contents=[PROMPT, *pages],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                # Use JSON Schema instead of OpenAPI response_schema.
                # Pydantic extra="forbid" emits additionalProperties=false;
                # the OpenAPI endpoint rejects it as "additional_properties".
                response_json_schema=Extraction.model_json_schema(),
                temperature=0,
            ),
        )
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
                    "model": selected_model}
        frame = pd.DataFrame(rows, columns=COLUMNS)
        message = f"{len(rows)} mediciones extraídas; pendientes de revisión."
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
                    message += f" Modelo solicitado: {selected_model}."
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

def validate_review(table, snapshot):
    if not snapshot:
        raise ValueError("Primero extrae un documento.")
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table, columns=COLUMNS)
    original = snapshot["rows"]
    if len(frame) != len(original):
        raise ValueError("No se permite agregar o eliminar filas de auditoría.")
    verified = []
    for i, (row, base) in enumerate(zip(frame.to_dict("records"), original), start=1):
        # Prevent changing the original provenance, including original AI value.
        for key in ("exam_datetime", "filename", "person_id", "age", "original_value"):
            if _string(row.get(key)) != _string(base.get(key)):
                raise ValueError(f"Fila {i}: no se permiten cambios en datos originales.")
        if not _string(row.get("section")) or not _string(row.get("measurement")):
            raise ValueError(f"Fila {i}: sección y medición obligatorias.")
        _decimal(row.get("value"))
        corrected = any(_string(row.get(k)) != _string(base.get(k))
                        for k in ("value", "unit", "section", "measurement"))
        comment = _string(row.get("correction_comment"))
        if corrected and not comment:
            raise ValueError(f"Fila {i}: describe la corrección en el comentario.")
        reviewed = row.get("reviewed") is True or str(row.get("reviewed")).lower() == "true"
        if not reviewed:
            raise ValueError(f"Fila {i}: marca revisado antes de guardar.")
        verified.append({
            "row_number": i,
            "exam_datetime": base["exam_datetime"], "filename": base["filename"],
            "person_id": base["person_id"], "age": base["age"],
            "section": _string(row["section"]),
            "measurement": _string(row["measurement"]),
            "value": _string(row["value"]), "unit": _string(row.get("unit")) or None,
            "original_value": base["original_value"], "original_section": base["section"],
            "original_measurement": base["measurement"], "original_unit": base["unit"],
            "was_corrected": corrected, "correction_comment": comment or None,
        })
    if not verified:
        raise ValueError("No hay mediciones para guardar.")
    return verified

def review_status(table, snapshot):
    try:
        rows = validate_review(table, snapshot)
        changed = sum(r["was_corrected"] for r in rows)
        return f"Revisión completa: {len(rows)} filas, {changed} correcciones, {len(rows)-changed} sin cambios."
    except ValueError as exc:
        return "Revisión pendiente: " + str(exc)

def save_audit(table, snapshot, consent, profile=None):
    if consent is not True:
        raise _ui_error("Debes aceptar el almacenamiento privado.")
    try:
        require_database_access(profile)
        rows = validate_review(table, snapshot)
        engine = _database_engine()
        try:
            with engine.begin() as con:
                # Migration must be applied by an administrator before this action.
                already = con.execute(text(
                    "SELECT extraction_id FROM hj_extraction_audits "
                    "WHERE source_sha256 = :sha"
                ), {"sha": snapshot["sha256"]}).scalar_one_or_none()
                if already:
                    raise ValueError("El archivo ya tiene una auditoría guardada.")
                audit_id = con.execute(text(
                    "INSERT INTO hj_extraction_audits "
                    "(source_sha256, filename, person_id, exam_datetime, age, model_name, raw_response) "
                    "VALUES (:sha, :filename, :person_id, :dt, :age, :model, CAST(:raw AS jsonb)) "
                    "RETURNING extraction_id"
                ), {"sha": snapshot["sha256"], "filename": snapshot["filename"],
                    "person_id": snapshot["header"]["person_id"],
                    "dt": datetime.fromisoformat(snapshot["header"]["exam_datetime"]),
                    "age": snapshot["header"]["age"], "model": snapshot["model"],
                    "raw": snapshot["raw_response"]}).scalar_one()
                con.execute(text(
                    "INSERT INTO hj_measurement_audits "
                    "(extraction_id, row_number, section, measurement, original_section, "
                    "original_measurement, original_value, original_unit, final_value, "
                    "final_unit, was_corrected, correction_comment, reviewed_at) "
                    "VALUES (:extraction_id, :row_number, :section, :measurement, "
                    ":original_section, :original_measurement, :original_value, :original_unit, "
                    ":value, :unit, :was_corrected, :correction_comment, now())"
                ), [{"extraction_id": audit_id, **r} for r in rows])
            return f"Auditoría privada guardada: {len(rows)} mediciones; {sum(r['was_corrected'] for r in rows)} corregidas."
        finally:
            engine.dispose()
    except (ValueError, PermissionError) as exc:
        raise _ui_error(str(exc)) from exc
    except Exception as exc:
        raise _ui_error("Error al guardar auditoría. Revisa migración 004 y la conexión privada.") from exc
