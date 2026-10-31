"""Regresiones sintéticas de OCR para ambos diseños InBody.

No se almacenan ni publican documentos de usuarios.
"""
from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from PIL import Image

from inbody_mvp.extractor import DocumentError, extract_document


def image_bytes():
    buf = BytesIO()
    Image.new("RGB", (1000, 1400), "white").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.parametrize("message", ["CUDA out of memory", "reader internal failure"])
def test_image_ocr_error_is_explicit_without_leaking_runtime_details(message):
    def failing_ocr(_image):
        raise RuntimeError(message)

    with pytest.raises(DocumentError) as err:
        extract_document("synthetic.jpg", image_bytes(), ocr=failing_ocr)
    assert "Falló el motor OCR" in str(err.value)
    assert "RuntimeError" in str(err.value)
    assert message not in str(err.value)


def test_empty_ocr_raises_instead_of_fake_zero_measurements():
    with pytest.raises(DocumentError, match="no reconoció texto"):
        extract_document("synthetic.jpg", image_bytes(), ocr=lambda _: [])


def test_empty_string_ocr_raises_for_images():
    with pytest.raises(DocumentError, match="no reconoció texto"):
        extract_document("synthetic.png", make_png(), ocr=lambda _: "")


def make_png():
    buf = BytesIO()
    Image.new("RGB", (200, 250), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_scanned_pdf_without_text_and_failed_ocr_is_rejected():
    pdf = fitz.open()
    pdf.new_page()
    data = pdf.tobytes()
    pdf.close()

    def failing_ocr(_image):
        raise RuntimeError("Contains private document info")

    with pytest.raises(DocumentError) as err:
        extract_document("scan.pdf", data, ocr=failing_ocr)
    assert "Falló el motor OCR" in str(err.value)
    assert "private document" not in str(err.value)


def test_both_layouts_accept_structured_ocr_without_false_success():
    # Only checks the common OCR shape; detailed spatial extraction has
    # separate English 580 and Spanish silhouette tests.
    detections = [
        ([[50, 50], [400, 50], [400, 80], [50, 80]],
         "Body Composition Analysis", .99),
        ([[50, 90], [400, 90], [400, 120], [50, 120]],
         "Weight 75.5 kg", .99),
    ]
    result = extract_document("synthetic.jpg", image_bytes(), ocr=lambda _: detections)
    assert result.texto_por_pagina
    assert "Body Composition Analysis" in result.texto_por_pagina[0]
    assert result.tipo_archivo == "jpg"
