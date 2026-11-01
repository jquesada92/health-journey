"""Synthetic regressions for real two-column InBody header layouts.

Never commit original InBody pictures, identifiers, or health metrics.
Tests mock OCR blocks with coordinates instead of running GPU inference.
"""
from io import BytesIO

import pytest
from PIL import Image

from inbody_mvp.extractor import extract_document
from inbody_mvp.layouts import extract_header_exam_timestamp


def boxes(*items):
    """EasyOCR-compatible boxes at normalized centers on a 1640x2310 sheet."""
    width, height = 1640, 2310
    out = []
    for value, x, y in items:
        px, py = x * width, y * height
        out.append((
            [[px - 13, py - 7], [px + 13, py - 7],
             [px + 13, py + 7], [px - 13, py + 7]],
            value, .97,
        ))
    return out


def synthetic_jpg():
    buf = BytesIO()
    Image.new("RGB", (1640, 2310), "white").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.parametrize("model_header,label,date_value,clock,expected", [
    ("[InBody580]", "Test Date / Time", "04.10.2026.", "10:04",
     "2026-10-04T10:04:00"),
    ("Análisis de Magro por Segmentos", "Fecha / Hora del test",
     "26.01.2025.", "14:20", "2025-01-26T14:20:00"),
])
def test_mixed_columns_cannot_hide_real_header_exam_time(
    model_header, label, date_value, clock, expected,
):
    # Gender/Género and DOB appear on the SAME OCR rows. The previous
    # tokens_to_text() interleaved them and DATE_RE required start-of-line.
    tokens = boxes(
        (model_header, .57, .057),
        ("Gender", .36, .068),
        (label, .59, .068),
        ("Male", .36, .092),
        ("02.04.1992.", .40, .092),  # DOB; MUST NOT become exam date
        (date_value, .505, .092),
        (clock, .595, .092),
        ("72.4", .573, .19),
    )
    if model_header.startswith("Análisis"):
        tokens += boxes(
            ("Análisis de Grasa Segmental", .46, .566),
            ("Impedancia", .74, .735),
            ("Puntuación InBody", .72, .14),
        )

    assert extract_header_exam_timestamp(tokens, 1640, 2310) == expected
    report = extract_document("synthetic.jpg", synthetic_jpg(),
                              ocr=lambda _img: tokens)
    assert report.timestamp == expected
    assert report.timestamp[:10] != "1992-04-02"


def test_concatenated_date_and_time_in_single_ocr_detection():
    tokens = boxes(
        ("Test Date / Time", .57, .064),
        ("04.10.2026. 10:04", .56, .091),
    )
    assert extract_header_exam_timestamp(tokens, 1640, 2310) == (
        "2026-10-04T10:04:00"
    )


def test_exam_label_split_into_several_ocr_tokens():
    tokens = boxes(
        ("Fecha", .48, .066), ("/", .51, .066),
        ("Hora", .55, .066), ("del test", .61, .066),
        ("26.01.2025.", .5, .091), ("14:20", .60, .091),
    )
    assert extract_header_exam_timestamp(tokens, 1640, 2310) == (
        "2025-01-26T14:20:00"
    )


@pytest.mark.parametrize("items", [
    # A date in the birth-date column must never be selected.
    (("Test Date / Time", .6, .065),
     ("02.04.1992.", .38, .09), ("10:04", .60, .09)),
    # A time on a different line cannot be borrowed from another section.
    (("Test Date / Time", .6, .065),
     ("04.10.2026.", .50, .09), ("10:04", .6, .12)),
    # A year cannot be paired with invalid times or impossible dates.
    (("Test Date / Time", .6, .065),
     ("04.10.2026.", .50, .09), ("25:80", .60, .09)),
    (("Fecha / Hora del test", .6, .065),
     ("32.01.2025.", .50, .09), ("14:20", .60, .09)),
    # No label, so any random date elsewhere in header isn't trusted.
    (("Weight", .55, .065),
     ("04.10.2026.", .50, .09), ("10:04", .60, .09)),
])
def test_spatial_header_rejects_ambiguous_or_invalid_date(items):
    assert extract_header_exam_timestamp(boxes(*items), 1640, 2310) is None
