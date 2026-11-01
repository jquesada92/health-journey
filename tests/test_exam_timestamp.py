"""OCR timestamp must originate in the uploaded InBody report, not the user."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from inbody_mvp.extractor import parse_text
from inbody_mvp.storage import source_exam_timestamp

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("header,expected", [
    # Exact English/Spanish header formats printed in actual InBody exports,
    # rewritten as synthetic text so no patient image or identifier is committed.
    ("Test Date / Time\n04.10.2026. 10:04", "2026-10-04T10:04:00"),
    ("Fecha / Hora del test\n26.01.2025. 14:20", "2025-01-26T14:20:00"),
    ("Test Date / Time: 04.10.2026. 10:04", "2026-10-04T10:04:00"),
    ("Fecha / Hora del test: 26.01.2025. 14:20", "2025-01-26T14:20:00"),
    ("Test Date / Time\n2026.10.04. 10:04", "2026-10-04T10:04:00"),
    ("Fecha / Hora del test\n26/01/2025 14:20:30", "2025-01-26T14:20:30"),
    ("Fecha: 31/10/2026 09:35", "2026-10-31T09:35:00"),
    ("Fecha de examen: 31/10/2026 09:35", "2026-10-31T09:35:00"),
    ("Fecha de medición: 31.10.2026 09:35", "2026-10-31T09:35:00"),
    ("Fecha de la prueba: 31-10-2026 09:35:12", "2026-10-31T09:35:12"),
    ("Date of Test: 2026/10/31 09:35", "2026-10-31T09:35:00"),
    ("Measurement Date: 2026-10-31 09:35", "2026-10-31T09:35:00"),
    ("Test Date: 2026-10-31\nTime: 09:35", "2026-10-31T09:35:00"),
    ("Fecha de examen: 31/10/2026\nHora de examen: 09:35",
     "2026-10-31T09:35:00"),
])
def test_report_header_produces_canonical_timestamp(header, expected):
    extracted = parse_text([(header + "\nWeight 73.1 kg", "ocr")])
    assert extracted.timestamp == expected
    assert source_exam_timestamp(extracted.model_dump(mode="json")) == expected


def test_jpg_ocr_extracts_two_line_headers_as_report_timestamp():
    from io import BytesIO
    from PIL import Image
    from inbody_mvp.extractor import extract_document

    buf = BytesIO()
    Image.new("RGB", (300, 180), "white").save(buf, format="JPEG")
    report_image = buf.getvalue()
    for header, expected in (
        ("Test Date / Time\n04.10.2026. 10:04", "2026-10-04T10:04:00"),
        ("Fecha / Hora del test\n26.01.2025. 14:20", "2025-01-26T14:20:00"),
    ):
        result = extract_document(
            "synthetic.jpg",
            report_image,
            ocr=lambda _image: header + "\nWeight 72.5 kg",
        )
        assert result.timestamp == expected


@pytest.mark.parametrize("header", [
    "Test Date / Time\n04.10.2026.",
    "Fecha / Hora del test\n26.01.2025.",
    "Test Date / Time\n04.10.2026. 25:90",
    "Fecha / Hora del test\n32.01.2025. 14:20",
    "Test Date / Time\nFecha de nacimiento: 01.01.1990 10:04",
])
def test_header_never_invents_missing_or_invalid_exam_clock(header):
    result = parse_text([(header + "\nWeight 72 kg", "ocr")])
    assert result.timestamp is None


def test_birthdate_is_never_exam_date():
    result = parse_text([(
        "Birth Date: 1994-10-22\nDOB: 1994-10-22\nWeight 73 kg",
        "pdf_text",
    )])
    assert result.timestamp is None
    with pytest.raises(ValueError, match="fecha y hora"):
        source_exam_timestamp(result.model_dump(mode="json"))


@pytest.mark.parametrize("header", [
    "Fecha: 31/10/2026",
    "Fecha: 31/10/2026 25:80",
    "Fecha de medición: 32/10/2026 14:20",
    "Weight 73 kg",
])
def test_no_invented_time_or_date(header):
    result = parse_text([(header + "\nWeight 73 kg", "ocr")])
    assert result.timestamp is None
    with pytest.raises(ValueError, match="fecha y hora"):
        source_exam_timestamp(result.model_dump(mode="json"))


def test_gemini_exam_datetime_is_from_extraction_snapshot_only():
    source = (ROOT / "inbody_mvp/gemini_review.py").read_text()
    assert 'result.header.exam_datetime' in source
    assert 'datetime.fromisoformat(result.header.exam_datetime)' in source
    assert '"exam_datetime": base["exam_datetime"]' in source
