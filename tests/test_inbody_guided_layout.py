"""Synthetic UI contracts for the sequential InBody capture experience.

No uploads, model API, database connection or Gradio startup are required.
"""
import ast
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
INBODY = SOURCE.split('with gr.Tab("InBody Upload"):', 1)[1].split(
    'with gr.Tab("Training Hub"):', 1
)[0]


def _function(name):
    return next(n for n in ast.walk(TREE)
                if isinstance(n, ast.FunctionDef) and n.name == name)


def test_inbody_steps_follow_users_real_actions_in_order():
    titles = (
        "### 1. Carga tu examen",
        "### 2. Selecciona la IA y extrae las mediciones",
        "### 3. Revisa y corrige los resultados",
        "### 4. Valida todas las mediciones",
        "### 5. Guarda el examen en la base de datos",
    )
    positions = [INBODY.index(title) for title in titles]
    assert positions == sorted(positions)
    assert "flex-wrap:wrap" in INBODY  # step navigation wraps on mobile
    assert INBODY.count('### 1. Carga tu examen') == 1


def test_review_uses_full_width_table_with_collapsible_original():
    assert "with gr.Accordion(" in INBODY
    assert '"Ver examen original y comparar las mediciones"' in INBODY
    assert "height=420" in INBODY
    assert "gemini_preview = gr.Gallery(" in INBODY
    assert "gemini_table = gr.Dataframe(" in INBODY
    assert "with gr.Column(scale=7, min_width=550)" not in INBODY
    assert "correction_comment" in INBODY
    assert "**reviewed**" in INBODY


def test_validation_has_own_feedback_without_reusing_extraction_status():
    validate = INBODY.split('gemini_check.click(', 1)[1].split(
        'gr.Markdown(', 1
    )[0]
    assert "outputs=[gemini_review_status]" in validate
    assert "gemini_status" not in validate
    assert "gemini_review_status = gr.Markdown(" in INBODY


def test_success_clears_document_but_keeps_visible_receipt_and_session_optins():
    callback = _function("save_review_and_clear")
    body = ast.unparse(callback)
    assert "gr.Info(visible_message)" in body
    assert "return keep_components(11)" in body
    success_returns = [
        node.value for node in ast.walk(callback)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)
    ]
    assert len(success_returns) == 1
    assert len(success_returns[0].elts) == 11
    assert isinstance(success_returns[0].elts[0], ast.Name)
    assert success_returns[0].elts[0].id == "visible_message"
    assert "session_ai_consent" not in body
    assert "session_db_consent" not in body
    save_outputs = INBODY.split('gemini_save.click(', 1)[1].split(
        'concurrency_limit=1,', 1
    )[0]
    assert "gemini_review_status" in save_outputs


def test_new_file_resets_review_only_and_not_session_permissions():
    assert "outputs=[gemini_snapshot]" in INBODY
    assert "gemini_review_status" in INBODY.split("gemini_upload.upload(", 1)[1]
    clear = INBODY.split("gr.ClearButton(", 1)[1]
    assert "gemini_review_status" in clear
    assert "session_ai_consent" not in clear
    assert "session_db_consent" not in clear
