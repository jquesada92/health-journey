"""Synthetic-only AI section detection and scoped OCR tests; no patient data."""
from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from inbody_mvp import section_ai
from inbody_mvp.extractor import extract_document


def boxes(*items):
    """EasyOCR response with 4-point boxes around invented text."""
    out = []
    for text, x, y, score in items:
        out.append(([[x, y], [x+35, y], [x+35, y+14],
                     [x, y+14]], text, score))
    return out


def image_bytes():
    b = BytesIO()
    Image.new("RGB", (800, 1000), "white").save(b, "JPEG")
    return b.getvalue()


def test_real_pretrained_model_adapter_is_called_with_image(monkeypatch):
    seen = []
    class FakePaddleModel:
        def predict(self, array, batch_size):
            seen.append((array.shape, batch_size))
            return [
                SimpleNamespace(json={
                    "res": {"boxes": [
                        {"label": "table", "score": .92,
                         "coordinate": [10, 100, 400, 320]},
                        {"label": "chart", "score": .2,
                         "coordinate": [10, 400, 400, 600]},
                        {"label": "unknown", "score": .99,
                         "coordinate": [0, 0, 800, 1000]},
                    ]}
                })
            ]
    monkeypatch.setattr(section_ai, "_layout_model", lambda: FakePaddleModel())
    regions = section_ai.ai_detect_layout(Image.new("RGB", (800, 1000)))
    assert seen == [((1000, 800, 3), 1)]
    assert len(regions) == 1
    assert regions[0].label == "table"
    assert regions[0].box == (10, 100, 400, 320)


def test_ai_detection_precedes_cropped_ocr_and_maps_to_page():
    page = Image.new("RGB", (800, 1000), "white")
    sequence = []
    regions = [
        section_ai.LayoutRegion("table", .95, (30, 100, 390, 240)),
        section_ai.LayoutRegion("chart", .90, (30, 500, 390, 700)),
        section_ai.LayoutRegion("text", .83, (400, 110, 780, 245)),
    ]

    def detector(_):
        sequence.append("ai-first")
        return regions

    def recognizer(crop):
        sequence.append("ocr")
        if crop.height < 500 and crop.width < 850:
            # The expected OCR order is based on the detector output.
            if sequence.count("ocr") == 1:
                return boxes(
                    ("Body Composition Analysis", 15, 5, .98),
                    ("Weight 73.3 kg", 110, 60, .94),
                )
            return boxes(
                ("Body Composition History", 15, 5, .98),
                ("Weight 67.2 kg", 100, 140, .99),
            )
        return []
    result = section_ai.inspect_sections(
        page, recognizer, detect=detector, max_sections=10,
    )
    assert sequence[0] == "ai-first"
    assert "ocr" in sequence
    assert result
    assert any(z.section == "body_composition" for z in result)
    assert any(z.section == "history" for z in result)
    assert all(z.detections for z in result)


def test_merge_excludes_history_even_if_ocr_score_is_high():
    current = boxes(("72.8", 150, 160, .65))
    region_current = section_ai.SectionOCR(
        section="body_composition", model_label="table", confidence=.95,
        box=(0, 0, 300, 300),
        detections=tuple(boxes(
            ("72.9", 150, 160, .94),
            ("Protein 12.2 kg", 70, 220, .97),
        )),
    )
    region_history = section_ai.SectionOCR(
        section="history", model_label="chart", confidence=.99,
        box=(0, 500, 450, 850),
        detections=tuple(boxes(("Weight 64.4 kg", 110, 610, .99))),
    )
    combined, notices = section_ai.merge_section_ocr(
        current, [region_current, region_history],
    )
    values = [z[1] for z in combined]
    assert "72.9" in values
    assert "72.8" not in values
    assert "Protein 12.2 kg" in values
    assert "Weight 64.4 kg" not in values
    assert any("historial" in x for x in notices)


def test_unknown_unlabelled_sections_never_add_measurements():
    region = section_ai.SectionOCR(
        section="unknown", model_label="table", confidence=.99,
        box=(0, 0, 400, 400),
        detections=tuple(boxes(("1000", 100, 100, .99))),
    )
    result, warnings = section_ai.merge_section_ocr([], [region])
    assert result == [] and warnings == []


def test_text_labels_for_sections_do_not_confuse_history_and_current():
    assert section_ai.classify_section("Body Composition History") == "history"
    assert section_ai.classify_section(
        "Análisis de la Composición Corporal"
    ) == "body_composition"
    assert section_ai.classify_section(
        "Análisis de Grasa Segmental"
    ) == "segmental_fat"
    assert section_ai.classify_section("random numbers 50 75 100") is None


def test_existing_ocr_still_used_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_AI_SECTION_OCR", raising=False)
    called = []
    def ocr(_):
        called.append("ocr")
        return boxes(("Weight 73.1 kg", 100, 100, .9))
    res = extract_document("synthetic.jpg", image_bytes(), ocr=ocr)
    assert called == ["ocr"]
    assert all("Sección" not in w for w in res.advertencias)


def test_section_model_failure_falls_back_without_leaking_details(monkeypatch):
    monkeypatch.setenv("ENABLE_AI_SECTION_OCR", "1")
    from inbody_mvp import extractor

    def failure(*_):
        raise RuntimeError("private paths and potential report data")

    monkeypatch.setattr(extractor, "inspect_sections", failure)
    with pytest.raises(extractor.DocumentError, match="no reconoció texto") as err:
        extract_document("synthetic.jpg", image_bytes(), ocr=lambda _: [])
    assert "private paths" not in str(err.value)


