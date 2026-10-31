"""Neon/PostgreSQL persistence for *manually reviewed* InBody examinations.

No network connection happens at import time. Only invoke from a private,
authenticated service or a localhost-only Gradio session. Never put DATABASE_URL
in source control or send medical reports to a public Space.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from .extractor import ExtractionResult
from .review import REVIEW_COLUMNS, ReviewedRow

ReportLanguage = Literal["ES", "EN", "UNKNOWN"]


class DuplicateExam(ValueError):
    """Identical source hash already stored."""


class StoredMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_label: str
    variable_medida: str
    categoria: str | None = None
    dimension: str | None = None
    segmento: str | None = None
    frecuencia_khz: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    unidad_medida: str | None = None
    valor_medida: float = Field(allow_inf_nan=False)
    pagina: int | None = Field(default=None, ge=1)
    fuente: str | None = None


class ConfirmedExam(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_persona: str = Field(min_length=1, max_length=128)
    modelo_inbody: str | None = Field(default=None, max_length=128)
    timestamp: datetime
    edad: int | None = Field(default=None, ge=0, le=120)
    age_source: str | None = None
    idioma_reporte: ReportLanguage
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_type: Literal["pdf", "jpg", "jpeg", "png"]
    measurements: list[StoredMeasurement] = Field(min_length=1)

    @field_validator("id_persona")
    @classmethod
    def reject_blank_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Falta ID de persona.")
        return value.strip()


def prepare_confirmed_exam(
    extracted_data: dict,
    table: pd.DataFrame | list,
    person_id: str,
    model: str | None,
    timestamp: str,
    age: int | float | None,
    language: ReportLanguage,
) -> ConfirmedExam:
    """Transform reviewed UI rows into a validated, immutable transaction payload.

    Does not save anything, and never invents an absent number, unit or date.
    """
    extracted = ExtractionResult.model_validate(extracted_data)
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table, columns=REVIEW_COLUMNS)
    if frame.empty:
        raise ValueError("No hay mediciones para confirmar.")
    if not timestamp or not str(timestamp).strip():
        raise ValueError("Introduce y revisa la fecha y hora del examen antes de guardar.")
    records = []
    for index, raw in enumerate(frame.to_dict(orient="records"), start=1):
        def clean(value):
            if value is None or (isinstance(value, str) and not value.strip()):
                return None
            try:
                if bool(pd.isna(value)):
                    return None
            except (TypeError, ValueError):
                pass
            return value
        row = {key: clean(raw.get(key)) for key in ReviewedRow.model_fields}
        for key in ("valor_medida", "frecuencia_khz"):
            if isinstance(row.get(key), str):
                row[key] = row[key].replace(",", ".")
        reviewed = ReviewedRow.model_validate(row)
        if reviewed.valor_medida is None:
            raise ValueError(f"Fila {index}: valor ambiguo. Corrige o elimina la fila antes de guardar.")
        records.append(StoredMeasurement(
            original_label=reviewed.original_label or "etiqueta_no_disponible",
            variable_medida=reviewed.variable_medida,
            categoria=clean(raw.get("categoria")),
            dimension=clean(raw.get("dimension")),
            segmento=reviewed.segmento,
            frecuencia_khz=reviewed.frecuencia_khz,
            unidad_medida=reviewed.unidad_medida,
            valor_medida=reviewed.valor_medida,
            pagina=clean(raw.get("pagina")),
            fuente=clean(raw.get("fuente")),
        ))
    parsed_age = None if age is None or age == "" or pd.isna(age) else age
    if parsed_age is not None:
        if float(parsed_age) != int(float(parsed_age)):
            raise ValueError("La edad debe ser un entero.")
        parsed_age = int(parsed_age)
    return ConfirmedExam(
        id_persona=person_id, modelo_inbody=model or None,
        timestamp=timestamp, edad=parsed_age, age_source=extracted.origen_edad,
        idioma_reporte=language,
        source_sha256=extracted.hash_sha256, source_type=extracted.tipo_archivo,
        measurements=records,
    )


def database_enabled() -> bool:
    """Never expose a write action in a public Hugging Face Space."""
    return (
        os.getenv("ENABLE_PERSISTENCE", "").strip().lower() in ("true", "1", "yes")
        and bool(os.getenv("DATABASE_URL"))
        and not os.getenv("SPACE_ID")
    )


def _database_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no configurado.")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Se requiere una URL PostgreSQL compatible con psycopg.")
    if "sslmode=" not in url:
        raise RuntimeError("DATABASE_URL debe habilitar SSL (sslmode=require).")
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)


def save_confirmed_exam(report: ConfirmedExam) -> str:
    """Insert person/exam/all metrics atomically; reject duplicate file hash."""
    if not database_enabled():
        raise RuntimeError("Persistencia deshabilitada. Usar solo una sesión local privada.")
    engine = _database_engine()
    try:
        with engine.begin() as connection:
            exists = connection.execute(
                text("SELECT exam_uuid FROM hj_exams WHERE source_sha256=:hash"),
                {"hash": report.source_sha256},
            ).scalar_one_or_none()
            if exists is not None:
                raise DuplicateExam("Este archivo ya existe en la base de datos.")
            person = connection.execute(text("""
                INSERT INTO hj_persons (id_persona, source_namespace)
                VALUES (:id_persona, 'inbody_unverified')
                ON CONFLICT (source_namespace, id_persona)
                DO UPDATE SET id_persona=EXCLUDED.id_persona
                RETURNING person_uuid
            """), {"id_persona": report.id_persona}).scalar_one()
            instant = report.timestamp
            tz_name = instant.tzname() if instant.tzinfo is not None else None
            naive_local = instant.replace(tzinfo=None)
            exam = connection.execute(text("""
                INSERT INTO hj_exams (
                    person_uuid, source_sha256, modelo_inbody,
                    exam_timestamp, timezone_name, edad, age_source,
                    idioma_reporte, language_basis, source_type
                ) VALUES (
                    :person, :hash, :model,
                    :tested_at, :timezone_name, :age, :age_source,
                    :language, 'human_review', :source_type
                ) RETURNING exam_uuid
            """), {
                "person": person, "hash": report.source_sha256,
                "model": report.modelo_inbody, "tested_at": naive_local,
                "timezone_name": tz_name, "age": report.edad,
                "age_source": report.age_source,
                "language": report.idioma_reporte, "source_type": report.source_type,
            }).scalar_one()
            connection.execute(text("""
                INSERT INTO hj_measurements (
                    exam_uuid, row_number, variable_medida, original_label,
                    categoria, dimension, segmento, frecuencia_khz,
                    unidad_medida, valor_medida, pagina, extraction_source
                ) VALUES (
                    :exam_uuid, :row_number, :variable_medida, :original_label,
                    :categoria, :dimension, :segmento, :frecuencia_khz,
                    :unidad_medida, :valor_medida, :pagina, :fuente
                )
            """), [
                {"exam_uuid": exam, "row_number": idx, **m.model_dump()}
                for idx, m in enumerate(report.measurements, start=1)
            ])
            return str(exam)
    except IntegrityError as exc:
        # Unique hash covers races between two requests.
        raise DuplicateExam("El examen ya existe o hay un conflicto de integridad.") from exc
    finally:
        engine.dispose()
