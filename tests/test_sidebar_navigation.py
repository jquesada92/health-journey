"""Contracts for the responsive sidebar and combined InBody AI action.

Synthetic tests only: no personal data, API keys or Gradio runtime required.
"""
import ast
from pathlib import Path

from inbody_mvp.navigation import NAV_SECTIONS, SIDEBAR_CSS

SOURCE = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _call(name):
    return [n for n in ast.walk(TREE)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == name]


def test_four_vertical_sidebar_entries_without_tab_overflow():
    assert tuple(key for key, _ in NAV_SECTIONS) == (
        "project", "inbody", "training", "coach"
    )
    assert len(_call("Sidebar")) == 1
    assert 'elem_id="hj-module-sidebar"' in SOURCE
    assert 'with gr.Column(elem_id="hj-module-content"):' in SOURCE
    assert 'elem_id="hj-panel-project"' in SOURCE
    assert 'visible=True, elem_id="hj-panel-project"' in SOURCE
    assert 'elem_id="hj-panel-inbody"' in SOURCE
    assert 'elem_id="hj-panel-training"' in SOURCE
    assert 'elem_id="hj-panel-coach"' in SOURCE
    assert len(_call("Tabs")) == 0
    assert len(_call("Tab")) == 0
    assert SOURCE.count('elem_classes="hj-nav-button"') == 4
    assert 'with gr.Tab("Historial' not in SOURCE
    assert 'gr.Markdown(PROJECT_OVERVIEW)' in SOURCE


def test_sidebar_selection_updates_all_columns_without_remounting():
    assert "outputs=[inbody_navbar, *module_panels, *nav_buttons]" in SOURCE
    assert 'gr.update(visible=(section == "inbody"))' in SOURCE
    assert "fn=lambda key=key: switch_module(key)" in SOURCE
    assert 'gr.update(visible=(key == section))' in SOURCE
    assert 'gr.update(variant="primary" if key == section else "secondary")' in SOURCE
    assert "css=INBODY_FLOW_CSS + SIDEBAR_CSS + COACH_CHAT_CSS" in SOURCE
    assert "#hj-module-content" in SIDEBAR_CSS
    assert "#hj-module-sidebar" in SIDEBAR_CSS
    assert "@media (max-width: 700px)" in SIDEBAR_CSS


def test_model_picker_refresh_extract_and_feedback_inside_one_group():
    body = SOURCE.split('with gr.Group(elem_id="hj-ai-extraction"):', 1)[1]
    group = body.split('gr.Markdown(\n                "### 3. Revisa', 1)[0]
    for name in (
        "gemini_model_selector = gr.Dropdown(",
        "gemini_models_button = gr.Button(",
        "gemini_models_status = gr.Markdown(",
        "gemini_extract = gr.Button(",
        "gemini_status = gr.Markdown(",
    ):
        assert name in group
    assert 'fn=check_models_with_popup' in group
    assert 'fn=extract_with_popup' in SOURCE
    assert 'consent = has_consent(request, "ai")' in SOURCE
    assert "Google Gemini recibirá el documento" in group


def test_existing_shared_consent_and_inbody_sticky_progress_remain():
    assert "fn=restore_session_consents" in SOURCE
    assert 'fn=progress_after_extract' in SOURCE
    assert 'fn=progress_after_validation' in SOURCE
    assert 'fn=progress_after_save' in SOURCE
    assert 'elem_id="hj-inbody-flow"' in SOURCE
    assert "gemini_upload_state, session_ai_consent," in SOURCE
    assert "gemini_model_selector, gemini_upload_preflight," in SOURCE
    assert "gemini_table, gemini_snapshot, session_db_consent," in SOURCE
    assert "header_exam_datetime, header_filename" in SOURCE
