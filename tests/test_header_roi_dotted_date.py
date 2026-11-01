"""Synthetic regression for right-column InBody header and dotted date."""
from inbody_mvp.layouts import extract_header_exam_timestamp
from inbody_mvp.section_review import propose_regions
from inbody_mvp.section_ai import LayoutRegion
from PIL import Image
import io


def test_right_column_header_and_dotted_date():
    def box(text, x, y, w=195):
        return ([[x,y],[x+w,y],[x+w,y+25],[x,y+25]], text, .99)
    tokens = [
        box("ID", 70, 70, 50),
        box("Edad", 600, 70, 80),
        box("Fecha / Hora del test", 1460, 70, 450),
        box("26.01.2025. 14:20", 1490, 113, 345),
    ]
    assert extract_header_exam_timestamp(tokens, 2048, 1400) == "2025-01-26T14:20:00"


def test_header_is_proposed_even_when_ai_only_finds_tables(monkeypatch):
    from inbody_mvp import section_review
    monkeypatch.setattr(section_review, "ai_detect_layout",
                        lambda _: [LayoutRegion("table", .91, (10, 100, 200, 250))])
    img = Image.new("RGB", (500, 800), "white")
    b = io.BytesIO()
    img.save(b, format="PNG")
    rows, metadata = propose_regions("synthetic.png", b.getvalue())
    assert rows[0][1] == "header"
    assert rows[0][2:6] == [0, 0, 500, 120]
    assert rows[1][1] == "other"
