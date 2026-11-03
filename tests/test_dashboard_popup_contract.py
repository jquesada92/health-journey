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
        "complete_coach_message", "recent_training_with_popup",
        "show_processed_filename",
        "upload_with_popup", "check_models_with_popup",
    ):
        node = _function(name)
        body = ast.unparse(node)
        assert "try:" in body, name
        assert "except" in body, name
    save = ast.unparse(_function("save_review_and_clear"))
    assert "return keep_components(16)" in save
    assert "if message.startswith('Guardado en Neon:')" in save
    assert "gr.Warning(message.replace('Neon', 'la base de datos'))" in save
    assert "gr.Info(visible_message)" in save
    progress = ast.unparse(_function("show_progress"))
    assert "return keep_components(13)" in progress


def test_plotly_report_row_and_score_display_within_same_dashboard():
    assert SOURCE.count('with gr.Accordion("Progreso histórico de InBody", open=False)') == 1
    assert 'progress_score = gr.Plot(' in SOURCE
    assert 'progress_section_history = gr.Plot(' in SOURCE
    assert 'progress_trends = gr.Plot(' in SOURCE
    assert '"Phase Angle"' in (ROOT / "inbody_mvp/progress_dashboard.py").read_text()
    assert "progress_score, progress_section_history" in SOURCE
    assert "gr.Tab(\"Dashboard público\")" not in SOURCE


def test_component_validation_badges_are_hidden_but_single_toast_is_preserved():
    # Gradio 6 paints div.validation-error badges in each component.
    # Suppress only those banners; never hide inputs or the global toast.
    assert "SINGLE_ERROR_MESSAGE_CSS = " in SOURCE
    assert ".gradio-container div.validation-error {" in SOURCE
    assert "display: none !important;" in SOURCE.split(
        "SINGLE_ERROR_MESSAGE_CSS =", 1
    )[1].split('"""', 2)[1]
    assert " + SINGLE_ERROR_MESSAGE_CSS," in SOURCE
    assert "show_error=False," in SOURCE
    assert "gr.Warning(str(message).replace(" in SOURCE
    review_status = SOURCE.split("gemini_review_status = gr.Markdown(", 1)[1].split(
        ")", 1
    )[0]
    assert "visible=False" in review_status


def test_review_error_is_one_toast_and_discards_previous_success():
    body = ast.unparse(_function("review_with_popup"))
    assert body.count("gr.Warning(") == 1
    assert "return (updated, new_snapshot, '')" in body
    assert "return (gr.update(), gr.update(), '')" in body
    assert "popup_error(" in body


def test_file_preflight_error_is_not_both_status_and_toast():
    body = ast.unparse(_function("show_processed_filename"))
    # The visible file-status message handles duplicate/unverified responses.
    assert "gr.Warning(" not in body
    assert "result['message']" in body
    assert "popup_error(" in body
    assert "return ('', None, gr.update(interactive=False))" in body
