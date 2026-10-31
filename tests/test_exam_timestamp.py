"""OCR timestamp must originate in the uploaded InBody report, not the user."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from inbody_mvp.extractor import parse_text
from inbody_mvp.storage import source_exam_timestamp

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("header,expected", [
    ("Fecha: 31/10/2026 09:35", "2026-10-31T09:35:00"),
    ("Fecha y hora: 31/10/2026 09:35", "2026-10-31T09:35:00"),
    ("Fecha/Hora: 31/10/2026 09:35:00", "2026-10-31T09:35:00"),
    ("Fecha & Hora: 31.10.2026 09:35", "2026-10-31T09:35:00"),
    ("Test Date / Time: 2026-10-31 09:35", "2026-10-31T09:35:00"),
    ("Date & Time: 2026/10/31 09:35", "2026-10-31T09:35:00"),
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


def test_gradio_datetime_is_display_only_and_callbacks_take_extraction_state():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    widgets = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "timestamp" for t in n.targets)
    ]
    assert len(widgets) == 1
    call = widgets[0].value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    assert call.func.attr == "Textbox"
    interactive = next(k.value for k in call.keywords if k.arg == "interactive")
    assert isinstance(interactive, ast.Constant) and interactive.value is False

    def bound_inputs(callback):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "click":
                continue
            fn = next((k.value for k in node.keywords if k.arg == "fn"), None)
            if not isinstance(fn, ast.Name) or fn.id != callback:
                continue
            inputs = next((k.value for k in node.keywords if k.arg == "inputs"), None)
            assert isinstance(inputs, ast.List)
            return [x.id for x in inputs.elts if isinstance(x, ast.Name)]
        raise AssertionError(f"No se encontró el callback {callback}")

    for callback in ("download_draft", "save_reviewed"):
        names = bound_inputs(callback)
        assert "extraction_state" in names
        assert "timestamp" not in names
    assert source.count("source_exam_timestamp(state)") >= 2
    assert "source_exam_timestamp(extracted_state)" in source
