"""Chat visual regression checks; no personal records or external services."""
import ast
from pathlib import Path

import gradio as gr

from inbody_mvp.coach_chat_ui import COACH_CHAT_CSS, COACH_CHAT_HEADER_HTML


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
TREE = ast.parse(APP)


def test_chat_header_and_scoped_mobile_css():
    assert 'aria-label="Cabecera del asistente fitness"' in COACH_CHAT_HEADER_HTML
    assert "Asistente fitness" in COACH_CHAT_HEADER_HTML
    assert "Gemini" in COACH_CHAT_HEADER_HTML
    assert "#hj-coach-chatbot" in COACH_CHAT_CSS
    assert "#hj-chat-composer" in COACH_CHAT_CSS
    assert "position: sticky;" in COACH_CHAT_CSS
    assert "safe-area-inset-bottom" in COACH_CHAT_CSS
    assert "@media (max-width: 700px)" in COACH_CHAT_CSS
    assert "max-width: 89%" in COACH_CHAT_CSS
    assert "inbody_mvp" not in COACH_CHAT_CSS.lower()
    assert "<script" not in COACH_CHAT_HEADER_HTML.lower()


def test_real_gradio6_bubble_chatbot_supports_responsive_height():
    with gr.Blocks():
        chatbot = gr.Chatbot(
            label=None,
            show_label=False,
            container=False,
            layout="bubble",
            height="min(64dvh, 660px)",
            autoscroll=True,
            elem_id="hj-coach-chatbot",
            placeholder="Empieza a conversar.",
            buttons=[],
            feedback_options=None,
            value=[
                {"role": "user", "content": "¿Cuánto he progresado?"},
                {"role": "assistant", "content": "Necesito tus mediciones."},
            ],
        )
        question = gr.Textbox(
            label="Mensaje para el asistente",
            show_label=False, lines=1, max_lines=4,
            scale=8, min_width=170, elem_id="hj-chat-input",
        )
        send = gr.Button("Enviar", scale=1, min_width=90, elem_id="hj-chat-send")
    assert chatbot.layout == "bubble"
    assert chatbot.height == "min(64dvh, 660px)"
    assert chatbot.autoscroll is True
    assert [msg["role"] for msg in chatbot.value] == ["user", "assistant"]
    assert question.elem_id == "hj-chat-input"
    assert send.elem_id == "hj-chat-send"


def test_coach_model_stays_separate_and_privacy_callbacks_preserved():
    assert "from inbody_mvp.coach_chat_ui import COACH_CHAT_CSS, COACH_CHAT_HEADER_HTML" in APP
    assert "gr.HTML(COACH_CHAT_HEADER_HTML" in APP
    assert "css=INBODY_FLOW_CSS + SIDEBAR_CSS + COACH_CHAT_CSS" in APP
    assert "gemini_model_selector = gr.Dropdown(" in APP
    assert "coach_model = gr.Dropdown(" in APP
    assert 'with gr.Accordion("Mis objetivos, contexto y privacidad", open=False)' in APP
    assert 'elem_id="hj-chat-composer"' in APP
    assert 'elem_id="hj-coach-chatbot"' in APP
    assert 'layout="bubble"' in APP
    assert 'type="messages"' not in APP
    assert "session_coach_consent" in APP
    assert "fn=ask_coach" in APP
    assert "fn=coach_refresh_model_options, outputs=[coach_model]" in APP
    assert "outputs=[gemini_model_selector, gemini_models_status]" in APP
    assert "coach_question.submit(" in APP
    assert "coach_send.click(" in APP
    assert "coach_clear.click(" in APP
    assert "outputs=[coach_chat, coach_context_status, coach_question]" in APP
