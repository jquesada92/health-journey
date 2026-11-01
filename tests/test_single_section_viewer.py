"""Regression: no duplicate visual proposal gallery or temp path dependency."""
from pathlib import Path


def test_primary_review_uses_session_bytes():
    app = Path("app.py").read_text()
    assert "def snapshot_upload(" in app
    assert "def report_from_snapshot(" in app
    assert "fn=detect_report_sections, inputs=[upload_snapshot]" in app
    assert "fn=process_report, inputs=[upload_snapshot, approved_state]" in app
    assert "inputs=[upload_snapshot, visual_editor, sections_state]" in app


def test_only_single_editable_region_viewer():
    app = Path("app.py").read_text()
    assert "visual_editor = gr.HTML(" in app
    assert "proposal_preview = gr.Gallery(" not in app
    assert "region_preview = gr.Gallery(" not in app
