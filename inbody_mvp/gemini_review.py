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

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

COLUMNS = ["exam_datetime", "filename", "person_id", "age", "section",
           "measurement", "value", "unit", "original_value", "was_corrected",
           "correction_comment", "reviewed"]
PROMPT = """You are an expert visual document parser for InBody body-composition reports.
Your task is to extract ALL legible numeric measurements from the CURRENT examination
and return the requested JSON only. Reports may be in Spanish, English or another
language, and layouts differ by device model.

LANGUAGE AND NORMALIZATION (MANDATORY)
- ALL values of "section", "measurement", and "missing_or_unreadable" MUST be in
  ENGLISH, regardless of the language printed in the report.
- Translate labels by meaning into consistent English; do NOT use snake_case in
  "section" or "measurement". Use Title Case for section names and readable
  English measurement names. Never mix Spanish and English in these fields.
- Standard section names, when present:
  "Body Composition Analysis", "Muscle-Fat Analysis", "Obesity Analysis",
  "Segmental Lean Analysis", "Segmental Fat Analysis", "Segmental ECW Analysis",
  "ECW Ratio-Phase Angle", "Research Parameters", "Weight Control",
  "InBody Score", and "Impedance".
  For unfamiliar sections, translate their actual name into English instead
  of forcing an incorrect known section.
- Standard body segments are: "Right Arm", "Left Arm", "Trunk",
  "Right Leg", "Left Leg". Determine left/right from anatomical labels
  in the report, NOT from the side of the page.
- For segmental measurements always use the name
  "{English Body Segment} - {English Measurement}".
  Examples: "Right Arm - Lean Mass", "Left Leg - Fat Mass",
  "Trunk - Percent of Reference", "Right Arm - Phase Angle".
  Do not mislabel lean mass as weight or fat mass as lean mass.
- For whole-body measurements use the English name alone, e.g.
  "Total Body Water", "Protein", "Minerals", "Weight",
  "Skeletal Muscle Mass", "Body Fat Mass", "Body Fat Percentage",
  "Body Mass Index", "Waist-Hip Ratio", "Basal Metabolic Rate".
- Retain units as standard internationally recognized symbols
  (kg, L, %, kcal, kHz, Ω, °, kg/m², cm) when applicable.
  Do NOT translate numeric values or alter physical units; use null for
  genuinely unitless measurements. The InBody Score uses "points".

EXAM HEADER AND SPATIAL RELATIONSHIPS
- Capture only the current person's ID, exam date/time and age from the
  main header (header.person_id, header.exam_datetime, header.age).
- A value can be BELOW its label (ID above the ID number, Test Date/Time
  above its timestamp), or to the RIGHT of its label in a table row.
- Use spatial alignment, rows, columns, borders, nearby units and segment
  labels. Never read the report as one linear stream or swap neighboring
  measurements. Keep leading zeros in person_id.
- Format exam_datetime as YYYY-MM-DD HH:MM:SS. Do not infer an absent
  timestamp or calculate an age. Set missing header fields to null.
- Filename is supplied by Python, never guess the filename.

CURRENT EXAM ONLY
- NEVER extract values from "Body Composition History", "Historial de
  Composición Corporal", history plots, trend graphs or past exams.
  Even the most recent point in a historical chart is forbidden as a source.
- Numeric tick labels, reference intervals, normal ranges, target values,
  and percentage scales are NOT measured values. Explicitly reported
  current-exam percentages ARE measurements.
- Do not estimate anything from bar length, graph position or appearance.

EXTRACTION RULES
- Output ONE measurement JSON object per numeric result, including score,
  segmental masses, segmental percentages, research parameters, ECW,
  phase angle, weight control and all explicitly printed impedance values.
- "section" must contain ONLY the English section name, without the body
  region. "measurement" carries the English region if applicable.
- Always capture the InBody Score if legible:
  section="InBody Score", measurement="InBody Score", unit="points".
- Frequencies printed under "Impedance" must have their OWN row:
  section="Impedance", measurement="Right Arm - Frequency",
  value="50", unit="kHz".
  Store an associated impedance separately:
  section="Impedance", measurement="Right Arm - Impedance at 50 kHz",
  value="205.5", unit="Ω".
  Do not create a frequency_khz column. Do not duplicate a frequency for
  the same segment and value in the section.
- Store every number in "value" as a STRING exactly as printed:
  "8.20" stays "8.20", "0.370" stays "0.370", "75.0" stays "75.0".
  Never round, trim trailing zeros, or calculate a replacement value.
- If a measurement is illegible, omit it and describe the missing item
  in English in missing_or_unreadable. Never invent results.
- Do not emit nonnumeric descriptive labels as separate measurements.

OUTPUT
Return strictly valid JSON matching the supplied schema:
{
  "header": {"person_id": null, "exam_datetime": null, "age": null},
  "measurements": [
    {
      "section": "Segmental Lean Analysis",
      "measurement": "Right Arm - Lean Mass",
      "value": "3.69",
      "unit": "kg"
    }
  ],
  "missing_or_unreadable": []
}
These values are examples only; use values actually printed on the report.
Do not add extra JSON properties, comments, Markdown, or explanation.
"""
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
    if candidate.lower() in ("", "off", "disabled", "none") or candidate == primary_model:
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


def save_audit(table, snapshot, consent, confirm_overwrite=False, profile=None):
    """Consent-based write-only submission; never grants private read access.

    The anonymous database role has EXECUTE only on a validated stored
    procedure; it cannot SELECT personal data from audit tables.
    """
    if consent is not True:
        raise _ui_error("Debes autorizar el envío de las mediciones a Neon.")
    try:
        rows = validate_review(table, snapshot)
        if not audit_write_enabled():
            raise PermissionError(
                "La escritura por consentimiento no está configurada. "
                "Solicita configurar DEMO_DATABASE_URL con health_journey_demo_writer "
                "y ENABLE_ANONYMOUS_DEMO=1."
            )
        body = {
            "source_sha256": snapshot["sha256"],
            "filename": snapshot["filename"],
            "person_id": snapshot["header"]["person_id"],
            "exam_datetime": snapshot["header"]["exam_datetime"],
            "age": snapshot["header"]["age"],
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


