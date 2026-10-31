"""Human-review table and seven-column CSV draft for Health Journey.

The CSV is an unconfirmed draft: there is no persistence or identity verification.
"""
from __future__ import annotations

import csv
import io
import math
import re
from datetime import datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .extractor import ExtractionResult

REVIEW_COLUMNS = [
    "original_label", "variable_medida", "categoria", "dimension", "segmento",
    "frecuencia_khz", "unidad_medida", "valor_medida", "pagina", "fuente",
]
EXPORT_COLUMNS = [
    "id_persona", "modelo_inbody", "timestamp", "variable_medida",
    "unidad_medida", "valor_medida", "edad",
]


class ReviewedRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    original_label: str = ""
    variable_medida: str = "sin_clasificar"
    segmento: str | None = None
    frecuencia_khz: float | None = Field(default=None, ge=0)
    unidad_medida: str | None = None
    valor_medida: float | None = Field(default=None, allow_inf_nan=False)

    @field_validator("variable_medida", mode="before")
    @classmethod
    def empty_measurement_name(cls, value):
        if value is None or pd.isna(value) or str(value).strip() == "":
            return "sin_clasificar"
        return str(value).strip()


def review_table(result: ExtractionResult) -> pd.DataFrame:
    """Create an editable table without discarding unknown measurements."""
    return pd.DataFrame(
        [{key: getattr(measure, key) for key in REVIEW_COLUMNS} for measure in result.medidas],
        columns=REVIEW_COLUMNS,
    )


def _as_optional(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (ValueError, TypeError):
        pass
    return value


def _measurement_key(row: ReviewedRow) -> str:
    name = row.variable_medida
    if name == "sin_clasificar":
        suffix = re.sub(r"[^a-zA-Z0-9]+", "_", row.original_label).strip("_").lower()
        name = f"sin_clasificar__{suffix or 'medicion_desconocida'}"
    if row.segmento:
        name += "__" + re.sub(r"[^a-zA-Z0-9_]+", "_", row.segmento.strip().lower()).strip("_")
    if row.frecuencia_khz is not None:
        name += f"__{row.frecuencia_khz:g}khz"
    return name


def _csv_safe_text(value: str | None) -> str:
    """Prevent formula execution if opened in spreadsheet software."""
    value = value or ""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def export_draft_csv(
    table: pd.DataFrame,
    person_id: str | None,
    device_model: str | None,
    timestamp: str | None,
    age: float | int | None,
) -> str:
    """Validate edited rows and export draft; never invent a missing value."""
    if table is None or table.empty:
        raise ValueError("No hay mediciones para exportar.")
    if timestamp:
        try:
            datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise ValueError("Timestamp inválido; usar AAAA-MM-DDTHH:MM:SS.") from exc
    if _as_optional(age) is not None:
        if float(age) != int(float(age)) or not 0 <= int(age) <= 120:
            raise ValueError("Edad inválida (debe ser un entero entre 0 y 120).")
        age = int(age)
    else:
        age = None

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    for number, raw in enumerate(table.to_dict(orient="records"), start=1):
        cleaned = {key: _as_optional(raw.get(key)) for key in ReviewedRow.model_fields}
        try:
            # Decimal commas are common in reports in Spanish.
            for key in ("valor_medida", "frecuencia_khz"):
                if isinstance(cleaned[key], str):
                    cleaned[key] = cleaned[key].replace(",", ".")
            row = ReviewedRow.model_validate(cleaned)
        except ValidationError as exc:
            raise ValueError(f"Medición {number}: revisa valor o frecuencia.") from exc
        if row.valor_medida is not None and not math.isfinite(row.valor_medida):
            raise ValueError(f"Medición {number}: valor no finito.")
        writer.writerow([
            _csv_safe_text(person_id), _csv_safe_text(device_model),
            _csv_safe_text(timestamp), _csv_safe_text(_measurement_key(row)),
            _csv_safe_text(row.unidad_medida),
            "" if row.valor_medida is None else row.valor_medida,
            "" if age is None else age,
        ])
    return out.getvalue()
