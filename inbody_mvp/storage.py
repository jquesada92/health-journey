"""Neon/PostgreSQL persistence for *manually reviewed* InBody examinations.

No network connection happens at import time. Only invoke from a private,
authenticated service or a localhost-only Gradio session. Never put DATABASE_URL
in source control or send medical reports to a public Space.
"""
from __future__ import annotations

import os
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


def source_exam_timestamp(extracted_data: dict) -> str:
    """Return the timestamp recorded by the report extractor, never user input.

    Do not assume midnight, the current date or the Space's timezone when
    the OCR did not identify the examination's actual date AND time.
    """
    extracted = ExtractionResult.model_validate(extracted_data)
    if not extracted.timestamp:
        raise ValueError(
            "No se detectó la fecha y hora del examen en el documento. "
            "Verifica que el encabezado sea legible y vuelve a extraer; "
            "no se permite introducir un timestamp manual."
        )
    try:
        parsed = datetime.fromisoformat(extracted.timestamp)
    except ValueError as exc:
        raise ValueError(
            "La fecha y hora extraídas no tienen un formato válido."
        ) from exc
    if not 1 <= parsed.year <= 9999:
        raise ValueError("Fecha del examen fuera de rango.")
    return parsed.isoformat(timespec="seconds")


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
    verified_timestamp = source_exam_timestamp(extracted_data)
    if timestamp != verified_timestamp:
        raise ValueError(
            "La fecha del formulario no coincide con la extraída del reporte. "
            "Vuelve a extraer el documento."
        )
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table, columns=REVIEW_COLUMNS)
    if frame.empty:
        raise ValueError("No hay mediciones para confirmar.")
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
        for key in ("valor_medida",):
            if isinstance(row.get(key), str):
                row[key] = row[key].replace(",", ".")
        reviewed = ReviewedRow.model_validate(row)
        # Backward-compatible DB column: derive frequency from the metric name
        # without exposing an independent numeric frequency in the UI.
        import re
        frequency_match = re.search(r"__(\\d+(?:\\.\\d+)?)khz$", reviewed.variable_medida)
        measured_frequency = (
            float(frequency_match.group(1)) if frequency_match else reviewed.frecuencia_khz
        )
        if reviewed.valor_medida is None:
            raise ValueError(f"Fila {index}: valor ambiguo. Corrige o elimina la fila antes de guardar.")
        if not reviewed.original_label.strip():
            raise ValueError(f"Fila {index}: falta la etiqueta original de la medición.")
        records.append(StoredMeasurement(
            original_label=reviewed.original_label,
            variable_medida=reviewed.variable_medida,
            categoria=clean(raw.get("categoria")),
            dimension=clean(raw.get("dimension")),
            segmento=reviewed.segmento,
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
        timestamp=verified_timestamp, edad=parsed_age, age_source=extracted.origen_edad,
        idioma_reporte=language,
        source_sha256=extracted.hash_sha256, source_type=extracted.tipo_archivo,
        measurements=records,
    )


def database_enabled() -> bool:
    """Configured database connection; Spaces also need an explicit user allowlist.

    This only reports configuration readiness, not authorization for a request.
    """
    configured = (
        os.getenv("ENABLE_PERSISTENCE", "").strip().lower() in ("true", "1", "yes")
        and bool(os.getenv("DATABASE_URL"))
    )
    if not configured:
        return False
    if os.getenv("SPACE_ID"):
        return bool(os.getenv("HF_ALLOWED_USERS", "").strip())
    return True


def require_report_access(oauth_profile=None) -> None:
    """Allow OCR and CSV on the same Space as the public dashboard.

    Public dashboards expose only approved views through PUBLIC_DATABASE_URL.
    OCR upload is a separate unauthenticated endpoint: real reports MUST be
    anonymized before upload if the Space itself is publicly accessible.
    This check never grants database read/write permissions.
    """
    return None


def require_database_access(oauth_profile=None) -> None:
    """Authorize EVERY private Neon read/write against HF OAuth username.

    Unlike OCR/CSV, private data must never be accessible anonymously.
    """
    if not database_enabled():
        raise PermissionError("Conexión Neon deshabilitada o incompleta.")
    require_report_access(oauth_profile)
    if os.getenv("SPACE_ID"):
        allowed = {
            part.strip().casefold()
            for part in os.getenv("HF_ALLOWED_USERS", "").split(",")
            if part.strip()
        }
        username = getattr(oauth_profile, "username", None)
        if (
            not allowed
            or not isinstance(username, str)
            or username.strip().casefold() not in allowed
        ):
            raise PermissionError(
                "Para guardar o consultar datos privados en Neon, inicia sesión "
                "con un usuario autorizado de Hugging Face."
            )


def load_measurement_history(
    person_id: str, oauth_profile=None, limit: int = 250
) -> list[dict]:
    """Read confirmed measurements for the explicitly requested InBody ID.

    Single-owner MVP: the HF allowlist is the security boundary.
    A multiuser app must introduce owner-scoped row-level authorization.
    """
    require_database_access(oauth_profile)
    person_id = str(person_id or "").strip()
    if not person_id or len(person_id) > 128:
        raise ValueError("Introduce un ID de persona válido para consultar el historial.")
    limit = max(1, min(int(limit), 500))
    engine = _database_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT e.exam_timestamp, e.modelo_inbody, e.idioma_reporte,
                       m.variable_medida, m.original_label, m.unidad_medida,
                       m.valor_medida, m.segmento, e.edad
                FROM hj_measurements m
                JOIN hj_exams e ON e.exam_uuid = m.exam_uuid
                JOIN hj_persons p ON p.person_uuid = e.person_uuid
                WHERE p.id_persona = :person_id
                ORDER BY e.exam_timestamp DESC NULLS LAST, m.row_number
                LIMIT :row_limit
            """), {"person_id": person_id, "row_limit": limit}).mappings().all()
            return [
                {
                    **dict(row),
                    "exam_timestamp": (
                        row["exam_timestamp"].isoformat(timespec="seconds")
                        if row["exam_timestamp"] else None
                    ),
                    "valor_medida": (
                        float(row["valor_medida"])
                        if row["valor_medida"] is not None else None
                    ),
                } for row in rows
            ]
    finally:
        engine.dispose()


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


def save_confirmed_exam(report: ConfirmedExam, oauth_profile=None, publish: bool = False) -> str:
    """Insert person/exam/all metrics atomically; reject duplicate file hash."""
    require_database_access(oauth_profile)
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
                    idioma_reporte, language_basis, source_type,
                    public_release_approved_at
                ) VALUES (
                    :person, :hash, :model,
                    :tested_at, :timezone_name, :age, :age_source,
                    :language, 'human_review', :source_type,
                    CASE WHEN :publish THEN now() ELSE NULL END
                ) RETURNING exam_uuid
            """), {
                "person": person, "hash": report.source_sha256,
                "model": report.modelo_inbody, "tested_at": naive_local,
                "timezone_name": tz_name, "age": report.edad,
                "age_source": report.age_source,
                "language": report.idioma_reporte, "source_type": report.source_type,
                "publish": bool(publish),
            }).scalar_one()
            connection.execute(text("""
                INSERT INTO hj_measurements (
                    exam_uuid, row_number, variable_medida, original_label,
                    categoria, dimension, segmento,
                    unidad_medida, valor_medida, pagina, extraction_source
                ) VALUES (
                    :exam_uuid, :row_number, :variable_medida, :original_label,
                    :categoria, :dimension, :segmento,
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
