import csv
import io

import fitz
import pytest
from PIL import Image

from inbody_mvp.extractor import DocumentError, classify_measure, extract_document, parse_text, validate_file


def fake_pdf(text):
    pdf = fitz.open()
    page = pdf.new_page()
    y = 72
    for line in text.splitlines():
        page.insert_text((70, y), line, fontsize=10)
        y += 16
    data = pdf.tobytes()
    pdf.close()
    return data


def fake_image(kind="PNG"):
    stream = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(stream, format=kind)
    return stream.getvalue()


def test_pdf_native_text_and_phase_angle():
    payload = fake_pdf("\n".join([
        "ID: 8-123-456", "InBody 770", "Fecha: 28/10/2026 09:35", "Fecha nacimiento: 15/05/1992",
        "Weight 75.2 kg", "Phase Angle Left Leg (50 kHz) 5.8 °",
        "Unknown Bio Metric 9.2 %", "Segmental Lean Mass Left Leg 8.3 kg",
    ]))
    out = extract_document("report.PDF", payload)
    assert out.id_persona == "8-123-456"
    assert out.modelo_inbody == "InBody 770"
    assert out.edad == 34 and out.origen_edad == "calculada_desde_fecha_nacimiento"
    assert out.timestamp == "2026-10-28T09:35:00"
    assert len(out.medidas) == 4
    pha = next(x for x in out.medidas if x.variable_medida == "phase_angle")
    assert (pha.segmento, pha.frecuencia_khz, pha.unidad_medida) == ("left_leg", 50.0, "°")
    assert any(x.variable_medida == "sin_clasificar" for x in out.medidas)


def test_jpg_and_png_dispatch_to_ocr():
    sample = "ID: ABC-123\nInBody 570\nWeight 70.0 kg\nPhase Angle 6.2 °"
    for suffix, image_format in (("jpg", "JPEG"), ("jpeg", "JPEG"), ("png", "PNG")):
        called = []
        def fake_ocr(image):
            called.append(image.size)
            return sample
        result = extract_document(f"scan.{suffix}", fake_image(image_format), ocr=fake_ocr)
        assert called == [(600, 400)]
        assert len(result.medidas) == 2
        assert all(x.fuente == "ocr" for x in result.medidas)


def test_scanned_pdf_falls_back_to_ocr():
    pdf = fitz.open()
    pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    out = extract_document("scan.pdf", data, ocr=lambda _: "Weight 72.0 kg\nBody Fat Mass 12.0 kg")
    assert len(out.medidas) == 2
    assert all(x.fuente == "ocr" for x in out.medidas)


def test_does_not_invent_missing_units_or_dates():
    out = parse_text([("InBody 570\nWeight 75.0\nNovel Label 8.0", "pdf_text")])
    assert out.timestamp is None and out.edad is None
    assert out.medidas[0].unidad_medida is None
    assert out.medidas[1].variable_medida == "sin_clasificar"


def test_rejects_renamed_files_and_unknown_extension():
    with pytest.raises(DocumentError):
        validate_file("renamed.png", fake_pdf("Weight 75 kg"))
    with pytest.raises(DocumentError):
        validate_file("evil.svg", b"<svg></svg>")
    with pytest.raises(DocumentError):
        validate_file("empty.pdf", b"")


def test_rejects_corrupt_image():
    with pytest.raises(DocumentError):
        extract_document("oops.png", b"\x89PNG\r\n\x1a\ncorrupted")


def test_page_limit():
    pdf = fitz.open()
    for _ in range(9):
        pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    with pytest.raises(DocumentError):
        extract_document("many.pdf", data, ocr=lambda _: "")


def test_ambiguous_date_never_used_to_invent_hour():
    out = parse_text([("Fecha: 31/10/2026\nAge: 33\nWeight 75 kg", "ocr")])
    assert out.edad == 33 and out.origen_edad == "reportada_no_calculada"
    assert out.timestamp is None


def test_classifiers_do_not_conflate_lean_and_muscle():
    assert classify_measure("Segmental Lean Mass Left Leg", "kg")[0] == "segmental_lean_mass"
    assert classify_measure("Skeletal Muscle Mass", "kg")[0] == "skeletal_muscle_mass"


def test_repeated_lines_deduplicated_per_page():
    out = parse_text([("Weight 72 kg\nWeight 72 kg", "ocr")])
    assert len(out.medidas) == 1
