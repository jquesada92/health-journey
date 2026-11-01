"""Offline tests for visual debugging without downloading model weights."""
import io
from PIL import Image

from inbody_mvp.visual_debug import render_debug


def _image_bytes():
    image = Image.new("RGB", (120, 90), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_visual_debug_ocr_boxes(monkeypatch):
    monkeypatch.setenv("ENABLE_AI_SECTION_OCR", "0")

    def ocr(_image):
        return [([[10, 10], [70, 10], [70, 26], [10, 26]], "237", 0.97)]

    pictures, rows, status = render_debug("synthetic.png", _image_bytes(), ocr)
    assert len(pictures) == 1
    assert pictures[0].size == (120, 90)
    assert len(rows) == 1
    assert rows[0][:4] == [1, "EasyOCR", "237", 0.97]
    assert "desactivada" in status


def test_visual_debug_ai_detector(monkeypatch):
    from inbody_mvp import visual_debug
    from inbody_mvp.section_ai import LayoutRegion

    monkeypatch.setenv("ENABLE_AI_SECTION_OCR", "1")
    monkeypatch.setattr(visual_debug, "ai_detect_layout", lambda _image: [
        LayoutRegion("table", 0.93, (5, 5, 90, 70)),
    ])
    pictures, rows, status = render_debug("synthetic.png", _image_bytes(), lambda _: [])
    assert len(pictures) == 1
    assert rows[0][1:4] == ["IA layout", "table", 0.93]
    assert "activada" in status
