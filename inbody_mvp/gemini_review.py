"""Opt-in Gemini comparison for anonymized InBody documents.

Never called by the baseline local extractor. No persistence, cache, telemetry,
patient identifiers, or raw remote exception messages. Suggestions cannot be
written to Neon directly; a person must compare them against the original.
"""
from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field

from .extractor import MAX_UPLOAD_BYTES, validate_file

ALLOWED_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)
SUGGESTION_COLUMNS = [
    "seccion", "variable", "segmento", "valor_original",
    "unidad", "pagina", "evidencia",
]
_NUMERIC = re.compile(r"^[+-]?\d{1,6}(?:[.,]\d{1,5})?$")


class SuggestedMeasurement(BaseModel):
    section: str = Field(max_length=100)
    variable: str = Field(max_length=120)
    segment: str | None = Field(default=None, max_length=80)
    raw_value: str = Field(max_length=32)
    unit: str | None = Field(default=None, max_length=40)
    page: int = Field(ge=1, le=8)
    evidence: str = Field(max_length=240)


class SuggestedReport(BaseModel):
    measurements: list[SuggestedMeasurement] = Field(default_factory=list, max_length=250)


PROMPT = """Read this ANONYMIZED InBody report as a document with spatial structure.
Extract only measurements of the current examination, not axes, ranges,
reference percentages, normative intervals, historical graphs or calculations.
Do not include any person's name, ID, date of birth or other identifiers.
For each visible measurement, return:
- section: the exact table/section title when readable;
- variable: the metric label, with frequency (kHz) as part of this label
  only when explicitly shown and relevant to that measurement;
- segment: left/right arm, leg, trunk, whole body or null if not printed;
- raw_value: EXACT printed numeric characters AS A STRING, preserving all
  decimal places and trailing zeroes (for example '8.20' != '8');
- unit: the unit as printed, or null if absent; do not infer;
- page: page number, starting at 1;
- evidence: brief adjacent text that supports the label/value association.
Respect whether values are to the left, right, or beneath their labels.
Never guess unreadable values. Omit a measurement rather than invent it.
Exclude history/previous tests completely. Return only JSON for the schema.
"""


def gemini_review_enabled() -> bool:
    return os.getenv("ENABLE_GEMINI_REVIEW", "").lower() in {"1", "true", "yes"}


def review_with_gemini(
    filename: str,
    data: bytes,
    *,
    consent: bool,
    model: str = "gemini-2.5-flash",
) -> list[list]:
    """Return untrusted suggestions; requires explicit opt-in for each invocation.

    Do not convert raw_value to float: 8.20 must remain 8.20 for visual QA.
    """
    if not consent:
        raise PermissionError("Debes confirmar que el archivo está anonimizado y autorizar el envío a Google.")
    if not gemini_review_enabled():
        raise RuntimeError("La comparación con Gemini no está habilitada en este entorno.")
    if model not in ALLOWED_MODELS:
        raise ValueError("Modelo Gemini no permitido.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Archivo demasiado grande.")
    kind = validate_file(filename, data)
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Falta configurar GEMINI_API_KEY en Secrets de Hugging Face.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Falta instalar la dependencia opcional google-genai.") from exc

    # No upload to Files API, no file retained by our code. Google receives
    # the bytes in the model request and applies its own data-use terms.
    mime = {"pdf": "application/pdf", "jpeg": "image/jpeg", "png": "image/png"}[kind]
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=data, mime_type=mime), PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SuggestedReport,
                temperature=0,
                max_output_tokens=8192,
            ),
        )
        if not response.text:
            raise ValueError("Respuesta vacía")
        report = SuggestedReport.model_validate_json(response.text)
    except Exception as exc:
        # Provider errors can contain request snippets, file metadata or IDs.
        raise RuntimeError(
            "No se completó la revisión con Gemini. Revisa la cuota y la "
            "configuración del proveedor sin compartir el documento."
        ) from None

    result = []
    for measurement in report.measurements:
        if re.search(r"\bhistory\b|\bhistorial\b", measurement.section, re.I):
            continue
        raw = measurement.raw_value.strip()
        if not _NUMERIC.fullmatch(raw):
            continue  # Never coerce malformed or ambiguous printed values.
        if not measurement.evidence.strip() or not measurement.variable.strip():
            continue
        result.append([
            measurement.section.strip(), measurement.variable.strip(),
            measurement.segment, raw, measurement.unit, measurement.page,
            measurement.evidence.strip(),
        ])
    return result
