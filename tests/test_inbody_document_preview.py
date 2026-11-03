"""Synthetic PDF/image viewer and English naming regression tests.

No internet, Gemini key, personal report or Gradio runtime is needed.
"""
import io
from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image

from inbody_mvp.gemini_review import (
    PROMPT,
    MAX_UPLOAD_BYTES,
    render_document_preview,
)


def _png_bytes() -> bytes:
    image = Image.new("RGB", (200, 300), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    return data.getvalue()


def _pdf_bytes(page_count: int = 2) -> bytes:
    pdf = fitz.open()
    try:
        for i in range(page_count):
            page = pdf.new_page(width=220, height=330)
            page.insert_text((20, 40), f"Synthetic InBody Test Page {i+1}")
        return pdf.tobytes()
    finally:
        pdf.close()


def test_preview_renders_each_pdf_page_without_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    pages, status = render_document_preview({
        "filename": "synthetic.pdf", "data": _pdf_bytes(3),
    })
    assert len(pages) == 3
    assert [caption for _, caption in pages] == [
        "Página 1", "Página 2", "Página 3"
    ]
    assert all(isinstance(image, Image.Image) for image, _ in pages)
    assert all(image.width > 220 for image, _ in pages)
    assert "3 página(s)" in status


def test_preview_image_and_clear_are_supported():
    pages, status = render_document_preview({
        "filename": "synthetic.png", "data": _png_bytes(),
    })
    assert len(pages) == 1
    assert pages[0][0].size == (200, 300)
    assert render_document_preview(None)[0] == []


def test_preview_rejects_unsupported_extension():
    with pytest.raises(Exception, match="No se pudo visualizar"):
        render_document_preview({
            "filename": "synthetic.txt", "data": b"not a document",
        })


def test_preview_rejects_excess_pages_and_large_files(monkeypatch):
    with pytest.raises(Exception, match="No se pudo visualizar"):
        render_document_preview({
            "filename": "long.pdf", "data": _pdf_bytes(11),
        })
    monkeypatch.setattr("inbody_mvp.gemini_review.MAX_UPLOAD_BYTES", 3)
    with pytest.raises(Exception, match="No se pudo visualizar"):
        render_document_preview({
            "filename": "big.png", "data": _png_bytes(),
        })


def test_prompt_uses_only_english_canonical_labels():
    assert "MUST be in" in PROMPT and "ENGLISH" in PROMPT
    assert '"Body Composition Analysis"' in PROMPT
    assert '"Segmental Lean Analysis"' in PROMPT
    assert '"InBody Score"' in PROMPT
    assert '"Right Arm - Frequency"' in PROMPT
    assert '"Right Arm - Impedance at 50 kHz"' in PROMPT
    assert '"8.20" stays "8.20"' in PROMPT
    assert "NEVER extract values from" in PROMPT
    assert "missing_or_unreadable" in PROMPT


def test_review_ui_has_read_only_pdf_viewer_and_reset_on_upload():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert "gemini_preview = gr.Gallery(" in source
    assert 'buttons=["fullscreen"]' in source
    assert "show_share_button=False" not in source
    assert "fn=preview_with_popup" in source
    assert "outputs=[gemini_preview, gemini_preview_status]" in source
    # The old ClearButton is gone: a confirmed save resets the viewer
    # through save_review_and_clear, while a failed save preserves it.
    assert "gr.ClearButton(" not in source
    save_outputs = source.split("gemini_save.click(", 1)[1].split(
        "concurrency_limit=1,", 1
    )[0]
    assert "gemini_preview, gemini_preview_status," in save_outputs
    assert "gemini_table, gemini_status" in save_outputs
    assert "fn=save_review_and_clear" in source
    assert "gemini_snapshot, gemini_upload_preflight," in source
    assert "gemini_replace_existing," in source
    assert 'gemini_table, gemini_status, gemini_save_status,' in source
    assert 'gemini_review_status,' in source
    assert "outputs=[gemini_table, gemini_status, gemini_consent, gemini_save_status]" not in source


def test_original_document_is_vertical_and_visible_after_extraction():
    import ast
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert 'elem_id="hj-inbody-review-layout"' in source
    assert 'elem_id="hj-inbody-review-table"' in source
    assert 'elem_id="hj-inbody-review-document"' in source
    assert source.index('elem_id="hj-inbody-review-table"') < source.index(
        'elem_id="hj-inbody-review-document"'
    )
    assert "with gr.Accordion(\n                \"Ver examen original" not in source
    assert source.count("gemini_preview = gr.Gallery(") == 1
    assert "height=820" in source
    assert "preview=False" in source
    assert "visible=False," in source.split(
        'elem_id="hj-inbody-review-layout"', 1
    )[1].split('as inbody_review_layout:', 1)[0]
    assert "visible=True" in source.split("def progress_after_extract(", 1)[1].split(
        "gemini_extract.click(", 1
    )[0]
    # Extraction output and save-clear output continue using the exact
    # same Gradio gallery, without a second copy or another AI call.
    assert "outputs=[gemini_preview, gemini_preview_status]" in source
    assert "gemini_preview, gemini_preview_status," in source
    assert "render_document_preview(state)" in source
    layout_css = (
        Path(__file__).resolve().parents[1] / "inbody_mvp/inbody_flow.py"
    ).read_text()
    assert "#hj-inbody-review-layout {" in layout_css
    assert "#hj-inbody-review-document {" in layout_css
    assert "position: sticky" in layout_css
    assert "@media (max-width: 1100px)" in layout_css
    assert "flex-direction: column !important" in layout_css
