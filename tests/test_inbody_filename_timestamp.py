"""InBody report vs filename datetime: two formats, one audited timestamp.

This test uses synthetic names/images and a fake Gemini SDK. It cannot
read, mutate or expose the user's health records.
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image

from inbody_mvp.filename_timestamp import (
    exam_datetime_from_filename, normalize_report_exam_datetime,
)
from inbody_mvp import gemini_review, upload_preflight

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename,expected", [
    ("InBody_20261004095632.pdf", "2026-10-04 09:56:32"),
    ("scan_20240229112233_full.pdf", "2024-02-29 11:22:33"),
    ("machine_20251231235959.jpg", "2025-12-31 23:59:59"),
    ("test_20260901000102-other.PNG", "2026-09-01 00:01:02"),
])
def test_exact_first_underscore_filename_timestamp(filename, expected):
    assert exam_datetime_from_filename(filename) == expected


@pytest.mark.parametrize("filename", [
    "inbody.pdf",
    "inbody_20261004.jpg",
    "prefix_part_20261004095632.pdf",  # not after first underscore
    "prefix_202610040956321.pdf",      # longer than 14 digits
    "prefix_20261004095632x.pdf",      # not followed by delimiter
])
def test_unknown_filename_shape_never_guesses_date(filename):
    assert exam_datetime_from_filename(filename) is None


@pytest.mark.parametrize("filename", [
    "InBody_20260230000000.pdf",
    "InBody_20261301120000.pdf",
    "InBody_20251231246000.png",
    "InBody_20250101126060.pdf",
    "InBody_20230229081000.pdf",
])
def test_impossible_datetime_in_filename_is_rejected(filename):
    with pytest.raises(ValueError, match="inválida"):
        exam_datetime_from_filename(filename)


@pytest.mark.parametrize("report,expected", [
    ("04.10.2026 10:04", "2026-10-04 10:04:00"),
    ("04.10.2026. 10:04", "2026-10-04 10:04:00"),
    ("4.10.2026 9:04", "2026-10-04 09:04:00"),
    ("07.08.26 08:56", "2026-08-07 08:56:00"),
    ("26.01.2025. 14:20:30", "2025-01-26 14:20:30"),
    ("2026-10-04 10:04:00", "2026-10-04 10:04:00"),
])
def test_dd_mm_yyyy_hh_mm_report_date_normalized(report, expected):
    assert normalize_report_exam_datetime(report) == expected


@pytest.mark.parametrize("report", [
    "31.02.2026 12:20", "13.13.2026 12:20",
    "31.12.2026 26:11", "2026.10.04 10:04",
    "31.10.2026 10:99", "12.10.2026",
])
def test_invalid_or_ambiguous_report_timestamp_is_rejected(report):
    with pytest.raises(ValueError, match="(inválida|no reconocido)"):
        normalize_report_exam_datetime(report)


def _sample_png():
    buffer = io.BytesIO()
    Image.new("RGB", (96, 64), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _fake_gemini(monkeypatch, report_datetime):
    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    types.GenerateContentConfig = lambda **kwargs: kwargs
    genai.types = types
    genai.Client = lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(
            text=json.dumps({
                "header": {
                    "person_id": "synthetic-visitor",
                    "exam_datetime": report_datetime,
                    "age": 29,
                },
                "measurements": [{
                    "section": "Body Composition Analysis",
                    "measurement": "Weight",
                    "value": "74.90",
                    "unit": "kg",
                }],
                "missing_or_unreadable": [],
            })
        ))
    )
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", types)
    monkeypatch.setenv("GEMINI_API_KEY", "not-real-test-key")


@pytest.mark.parametrize("report_datetime", [
    "04.10.2026 10:04",       # real day-first report format
    "04.10.2026. 10:04",      # InBody trailing dot
    "2026-10-04 10:04:00",    # Gemini normalized output
    "03.10.2026 10:04",       # OCR date differs
    "imprecise OCR timestamp",  # filename rescues malformed OCR
    None,
])
def test_filename_is_authoritative_regardless_of_report_clock(
    monkeypatch, report_datetime,
):
    _fake_gemini(monkeypatch, report_datetime)
    frame, snapshot, message = gemini_review.extract_gemini(
        {
            "filename": "Body_20261004095632.png",
            "data": _sample_png(),
        },
        consent=True, selected_model="gemini-2.5-flash",
    )
    # Use a PNG filename because the in-memory synthetic image is PNG.
    assert snapshot["header"]["exam_datetime"] == "2026-10-04 09:56:32"
    assert snapshot["rows"][0]["exam_datetime"] == "2026-10-04 09:56:32"
    assert frame.iloc[0]["exam_datetime"] == "2026-10-04 09:56:32"
    assert snapshot["ai_header"]["exam_datetime"] == report_datetime
    assert snapshot["datetime_source"] == "filename"
    assert "2026-10-04 09:56:32" in message


def test_report_date_is_used_when_filename_has_no_timestamp(monkeypatch):
    _fake_gemini(monkeypatch, "04.10.2026 10:04")
    frame, snapshot, _ = gemini_review.extract_gemini(
        {"filename": "synthetic.png", "data": _sample_png()},
        consent=True, selected_model="gemini-2.5-flash",
    )
    assert frame.iloc[0]["exam_datetime"] == "2026-10-04 10:04:00"
    assert snapshot["datetime_source"] == "report"


def test_human_cannot_override_reliable_filename_date():
    snapshot = {
        "filename": "Body_20261004095632.pdf",
        "header": {
            "exam_datetime": "2026-10-04 09:56:32",
            "person_id": "synthetic-visitor", "age": 29,
        },
    }
    header = {
        "exam_datetime": "2026-10-04 10:04:00",
        "filename": snapshot["filename"],
        "person_id": "synthetic-visitor",
        "age": "29", "correction_comment": "PDF date differs",
    }
    with pytest.raises(ValueError, match="YYYYMMDDHHMMSS"):
        gemini_review._effective_header(snapshot, header)
    header["exam_datetime"] = snapshot["header"]["exam_datetime"]
    value, changed, comment = gemini_review._effective_header(snapshot, header)
    assert value["exam_datetime"] == "2026-10-04 09:56:32"
    assert changed is False
    assert comment == "PDF date differs"


def test_historical_correction_has_backup_and_atomic_validation():
    sql = (
        ROOT / "migrations/011_correct_inbody_dates_from_filenames.sql"
    ).read_text()
    assert "CREATE TABLE IF NOT EXISTS public.hj_exam_datetime_repair_history" in sql
    assert "original_exam_datetime timestamp NOT NULL" in sql
    assert "corrected_exam_datetime timestamp NOT NULL" in sql
    assert "to_timestamp(v_token, 'YYYYMMDDHH24MISS')" in sql
    assert "to_char(v_corrected, 'YYYYMMDDHH24MISS') <> v_token" in sql
    assert "INSERT INTO public.hj_exam_datetime_repair_history" in sql
    assert "UPDATE public.hj_extraction_audits" in sql
    assert sql.index("INSERT INTO public.hj_exam_datetime_repair_history") < (
        sql.index("UPDATE public.hj_extraction_audits")
    )
    assert "REVOKE ALL" in sql
    assert "DROP TABLE" not in sql
    assert "TRUNCATE" not in sql


def test_sql_replacement_guards_filename_datetime():
    sql = (
        ROOT / "migrations/010_private_inbody_filename_replace.sql"
    ).read_text()
    assert "v_stamp := substring(v_filename" in sql
    assert "v_exam IS DISTINCT FROM v_stamp_time" in sql
    assert "Filename and exam timestamp differ" in sql


def test_preflight_displays_file_timestamp_without_gemini(monkeypatch):
    monkeypatch.setattr(
        upload_preflight, "check_processed_filename",
        lambda *args, **kwargs: "Archivo nuevo: prueba sintética",
    )
    status = upload_preflight.preflight_processed_upload({
        "filename": "Body_20261004095632.pdf", "data": b"fake-data",
    })
    assert status["status"] == "new"
    assert "2026-10-04 09:56:32" in status["message"]
