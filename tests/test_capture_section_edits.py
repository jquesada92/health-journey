"""Capture section edits from canvas into table without approving extraction."""
import ast
from pathlib import Path


def test_capture_button_is_explicit_and_before_validate():
    source = Path("app.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'capture_sections_button = gr.Button("Capturar nuevas secciones y correcciones"' in source
    assert source.index("capture_sections_button.click(") < source.index("validate_sections_button.click(")
    assert "outputs=[regions_table, approved_state, region_status]" in source


def test_capture_does_not_approve_regions():
    source = Path("app.py").read_text(encoding="utf-8")
    block = source.split("def capture_section_edits(")[1].split("def approve_report_sections(")[0]
    assert "return rows, None," in block
    assert "report_from_snapshot(upload_state)" in block
