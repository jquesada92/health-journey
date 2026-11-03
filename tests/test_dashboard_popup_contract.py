"""No component error spam; dashboard replicates report trends with Phase Angle."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app.py").read_text()
TREE = ast.parse(SOURCE)


def _function(name):
    matches = [
        node for node in ast.walk(TREE)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def test_one_warning_popup_and_no_gr_error_callbacks():
    assert not any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Attribute)
        and isinstance(node.exc.func.value, ast.Name)
        and node.exc.func.value.id == "gr"
        and node.exc.func.attr == "Error"
        for node in ast.walk(TREE)
    )
    body = ast.unparse(_function("popup_error"))
    assert "gr.Warning(str(message).replace('Neon', 'la base de datos'))" in body
    assert "fallback" in body


def test_failed_events_preserve_component_values():
    for name in (
        "save_review_and_clear", "extract_with_popup",
        "review_with_popup", "preview_with_popup",
        "show_public_dashboard", "show_progress",
        "display_history", "display_audit_history",
        "show_processed_filename",
        "upload_with_popup", "check_models_with_popup",
    ):
        node = _function(name)
        body = ast.unparse(node)
        assert "try:" in body, name
        assert "except" in body, name
    save = ast.unparse(_function("save_review_and_clear"))
    assert "return keep_components(10)" in save
    assert "if message.startswith('Guardado en Neon:')" in save
    assert "gr.Warning(message.replace('Neon', 'la base de datos'))" in save
    assert "gr.Info(message.replace('Neon', 'la base de datos'))" in save
    progress = ast.unparse(_function("show_progress"))
    assert "return keep_components(13)" in progress


def test_plotly_report_row_and_score_display_within_same_dashboard():
    assert SOURCE.count('with gr.Tab("Dashboard")') == 1
    assert 'progress_score = gr.Plot(' in SOURCE
    assert 'progress_section_history = gr.Plot(' in SOURCE
    assert 'progress_trends = gr.Plot(' in SOURCE
    assert '"Phase Angle"' in (ROOT / "inbody_mvp/progress_dashboard.py").read_text()
    assert "progress_score, progress_section_history" in SOURCE
    assert "gr.Tab(\"Dashboard público\")" not in SOURCE
