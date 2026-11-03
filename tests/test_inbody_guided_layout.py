"""Synthetic UI contracts for the sequential InBody capture experience.

No uploads, model API, database connection or Gradio startup are required.
"""
import ast
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
INBODY = SOURCE.split('with gr.Column(visible=False, elem_id="hj-panel-inbody") as inbody_panel:', 1)[1].split(
    'with gr.Column(visible=False, elem_id="hj-panel-training") as training_panel:', 1
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
    # The navbar is outside the scrolling InBody panel so it stays viewport-fixed.
    assert 'elem_id="hj-inbody-flow"' in SOURCE
    assert "value=render_inbody_flow(1)" in SOURCE
    assert 'elem_id="hj-inbody-fixedbar"' not in INBODY
    assert INBODY.count('### 1. Carga tu examen') == 1


def _element_id(node):
    """Read literal Gradio element IDs without depending on UI whitespace."""
    if not isinstance(node, ast.With):
        return None
    for item in node.items:
        call = item.context_expr
        if isinstance(call, ast.Call):
            for kw in call.keywords:
                if (kw.arg == "elem_id" and isinstance(kw.value, ast.Constant)):
                    return kw.value.value
    return None


def test_document_is_alongside_editable_table_without_collapsible_panel():
    rows = [node for node in ast.walk(TREE)
            if _element_id(node) == "hj-inbody-review-layout"]
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row.items[0].context_expr.func, ast.Attribute)
    assert row.items[0].context_expr.func.attr == "Row"

    columns = [node for node in row.body
               if isinstance(node, ast.With)]
    assert [_element_id(node) for node in columns] == [
        "hj-inbody-review-table", "hj-inbody-review-document"
    ]
    table_code = ast.get_source_segment(SOURCE, columns[0])
    original_code = ast.get_source_segment(SOURCE, columns[1])
    assert "gemini_table = gr.Dataframe(" in table_code
    assert "gemini_preview = gr.Gallery(" in original_code
    assert "gemini_preview_status = gr.Markdown(" in original_code
    assert "height=820" in original_code
    assert "preview=False" in original_code
    assert "visible=False" in ast.get_source_segment(SOURCE, row.items[0].context_expr)
    assert "as inbody_review_layout:" in SOURCE
    assert 'buttons=["fullscreen"]' in original_code
    assert 'columns=1' in original_code
    assert 'object_fit="contain"' in original_code
    assert '"Ver examen original y comparar las mediciones"' not in INBODY
    assert INBODY.count("gemini_preview = gr.Gallery(") == 1
    assert INBODY.count("gemini_table = gr.Dataframe(") == 1
    assert "headers=GEMINI_DISPLAY_COLUMNS" in table_code
    assert "correction_comment" in INBODY
    assert "**reviewed**" in INBODY


def test_extraction_passes_duplicate_preflight_to_callback():
    extract = _function("extract_with_popup")
    required = [arg.arg for arg in extract.args.args[:4]]
    assert required == ["state", "consent", "model", "preflight"]
    extract_binding = INBODY.split("gemini_extract.click(", 1)[1].split(
        ").then(", 1
    )[0]
    assert "gemini_upload_preflight" in extract_binding
    assert "session_ai_consent" in extract_binding
    assert "gemini_model_selector" in extract_binding


def test_validation_has_own_feedback_without_reusing_extraction_status():
    validate = INBODY.split('gemini_check.click(', 1)[1].split(
        'gr.Markdown(', 1
    )[0]
    assert "outputs=[gemini_table, gemini_snapshot, gemini_review_status]" in validate
    assert "gemini_status" not in validate
    assert "gemini_review_status = gr.Markdown(" in INBODY


def test_success_clears_document_but_keeps_visible_receipt_and_session_optins():
    callback = _function("save_review_and_clear")
    body = ast.unparse(callback)
    assert "gr.Info(visible_message)" in body
    assert "return keep_components(16)" in body
    success_returns = [
        node.value for node in ast.walk(callback)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)
    ]
    assert len(success_returns) == 1
    assert len(success_returns[0].elts) == 16
    assert isinstance(success_returns[0].elts[0], ast.Name)
    assert success_returns[0].elts[0].id == "visible_message"
    assert "session_ai_consent" not in body
    assert "session_db_consent" not in body
    save_outputs = INBODY.split('gemini_save.click(', 1)[1].split(
        'concurrency_limit=1,', 1
    )[0]
    assert "gemini_review_status" in save_outputs


def test_new_file_resets_review_only_and_not_session_permissions():
    assert "outputs=[gemini_snapshot, gemini_upload_preflight]" in INBODY
    assert "gemini_review_status" in INBODY.split("gemini_upload.upload(", 1)[1]
    assert "gr.ClearButton(" not in INBODY
    assert "Limpiar examen (conservar permisos)" not in INBODY
    assert "session_ai_consent" not in INBODY.split("def upload_with_popup(", 1)[1]
    assert "session_db_consent" not in INBODY.split("def upload_with_popup(", 1)[1]
    assert "outputs=[inbody_flow, inbody_navigation_target]" in INBODY
    assert "js=INBODY_NEXT_STEP_JS" in INBODY
    # User header edits must remain interactive; programmatic form clearing
    # after save may not reactivate step 3 or undo the reset to step 1.
    assert "field.input(" in INBODY
    assert "field.change(" not in INBODY


def test_duplicate_preflight_is_checked_at_upload_and_before_gemini():
    assert "gemini_upload_preflight = gr.State(value=None)" in SOURCE
    assert "preflight_processed_upload(" in INBODY
    assert "interactive=status in" in INBODY
    extract = ast.unparse(_function("extract_with_popup"))
    assert extract.index("preflight_processed_upload(") < extract.index("extract_gemini(")
    assert extract.index("fresh['status'] == 'duplicate'") < extract.index("extract_gemini(")
    upload = INBODY.split("gemini_upload.upload(", 1)[1].split(
        'with gr.Accordion("Progreso histórico de InBody"', 1
    )[0]
    assert upload.index("fn=show_processed_filename") < upload.index("fn=preview_with_popup")
    assert "inputs=[gemini_upload_state, gemini_upload_preflight]" in upload


def test_reviewer_appears_only_after_successful_ai_extraction_and_resets():
    extracted = ast.unparse(_function("progress_after_extract"))
    assert "if snapshot is not None" in extracted
    assert "visible=True" in extracted
    assert "visible=False" in extracted
    assert "inbody_review_layout" in INBODY
    extract_event = INBODY.split("gemini_extract.click(", 1)[1].split(
        "gemini_check.click(", 1
    )[0]
    assert "inbody_review_layout" in extract_event
    saved = ast.unparse(_function("progress_after_save"))
    assert "visible=False" in saved
    upload = ast.unparse(_function("advance_after_duplicate_check"))
    assert "visible=False" in upload


def test_consent_verification_endpoint_protected_by_original_signed_session():
    assert "verify_consent_session" in SOURCE
    assert 'Route("/privacy/verify", verify_consent_session, methods=["GET"])' in SOURCE
