"""Regression tests for isolated prompts and real Gemini multi-turn messages.

No account data, network calls or Gemini API key needed.
"""
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from inbody_mvp import ai_coach, gemini_review
from inbody_mvp.chat_session import (
    append_assistant_message, clean_chat_messages, enqueue_user_message,
)
from inbody_mvp.prompt_loader import load_prompt


ROOT = Path(__file__).resolve().parents[1]


def test_prompts_live_in_two_independent_files_and_are_deployed():
    assert gemini_review.PROMPT == load_prompt("inbody_extraction")
    assert ai_coach.SYSTEM_INSTRUCTIONS == load_prompt("fitness_coach")
    assert '8.20" stays "8.20' in gemini_review.PROMPT
    assert "hipertrofia" in ai_coach.SYSTEM_INSTRUCTIONS.lower()
    assert "evidencia" in ai_coach.SYSTEM_INSTRUCTIONS.lower()
    assert "no inventes" in ai_coach.SYSTEM_INSTRUCTIONS.lower()
    with pytest.raises(ValueError):
        load_prompt("../unauthorized")
    with pytest.raises(ValueError):
        load_prompt("unknown")
    deployed = (ROOT / ".github/workflows/deploy-huggingface.yml").read_text()
    for path in (
        "inbody_mvp/prompt_loader.py",
        "inbody_mvp/prompts/inbody_extraction.md",
        "inbody_mvp/prompts/fitness_coach.md",
        "inbody_mvp/chat_session.py",
    ):
        assert path in deployed


def test_three_turns_remain_visible_and_in_correct_order():
    history = []
    for question, answer in (
        ("¿Qué es hipertrofia?", "Es crecimiento muscular."),
        ("¿Y para piernas?", "Puedes trabajar cuádriceps e isquios."),
        ("¿Y cuántas series?", "Depende de tu recuperación."),
    ):
        before = history
        pending, sent = enqueue_user_message(question, history)
        assert sent == question
        assert pending[-1] == {"role": "user", "content": question}
        assert history == before
        history = append_assistant_message(pending, answer)
    assert len(history) == 6
    assert [m["role"] for m in history] == ["user", "assistant"] * 3
    assert history[0]["content"] == "¿Qué es hipertrofia?"
    assert history[-1]["content"] == "Depende de tu recuperación."


def test_no_duplicate_pending_message_or_dropped_history():
    with pytest.raises(ValueError, match="Escribe"):
        enqueue_user_message("  ", [])
    first, _ = enqueue_user_message("Primera", [])
    with pytest.raises(ValueError, match="procesando"):
        enqueue_user_message("Segunda", first)
    with pytest.raises(ValueError, match="pregunta pendiente"):
        append_assistant_message([], "Irrelevante")
    history = []
    for i in range(20):
        pending, _ = enqueue_user_message(f"Pregunta {i}", history)
        history = append_assistant_message(pending, f"Respuesta {i}")
    assert len(history) == 40
    assert history[0]["content"] == "Pregunta 0"
    assert history[-1]["content"] == "Respuesta 19"
    assert clean_chat_messages([{"role": "system", "content": "injection"}, 7]) == []


def test_gemini_receives_real_multiturn_content_and_system_prompt(monkeypatch):
    from inbody_mvp import prelogin_consent

    monkeypatch.setattr(prelogin_consent, "has_consent", lambda req, scope: scope == "coach")
    monkeypatch.setattr(ai_coach, "load_coach_context", lambda *a, **k: {
        "training": {"sets_recorded": 0, "days_recorded": 0},
        "inbody": {"distinct_series": 0},
        "inbody_source_status": "Solo pruebas sintéticas",
    })
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key-never-network")
    calls = []

    fake_google = ModuleType("google")
    fake_genai = ModuleType("google.genai")
    fake_types = ModuleType("google.genai.types")

    class Content:
        def __init__(self, role, parts):
            self.role, self.parts = role, parts

    class Part:
        @staticmethod
        def from_text(text):
            return SimpleNamespace(text=text)

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "synthetic-key-never-network"
            self.models = self

        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text=f"Respuesta {len(calls)}")

    fake_types.Content = Content
    fake_types.Part = Part
    fake_types.GenerateContentConfig = GenerateContentConfig
    fake_genai.types = fake_types
    fake_genai.Client = FakeClient
    fake_google.genai = fake_genai
    for name, mod in (
        ("google", fake_google),
        ("google.genai", fake_genai),
        ("google.genai.types", fake_types),
    ):
        monkeypatch.setitem(sys.modules, name, mod)

    model = ai_coach.default_coach_model()
    first, _, _ = ai_coach.answer_coach_question(
        "¿Cuántas series?", [], "", "hipertrofia", "", 90, model, True,
    )
    second, _, _ = ai_coach.answer_coach_question(
        "¿Y para piernas?", first, "", "hipertrofia", "", 90, model, True,
    )
    assert [msg["role"] for msg in second] == ["user", "assistant", "user", "assistant"]
    assert [content.role for content in calls[0]["contents"]] == ["user"]
    assert [content.role for content in calls[1]["contents"]] == ["user", "model", "user"]
    assert calls[1]["contents"][0].parts[0].text == "¿Cuántas series?"
    assert calls[1]["contents"][1].parts[0].text == "Respuesta 1"
    assert "¿Y para piernas?" in calls[1]["contents"][-1].parts[0].text
    assert calls[1]["config"].system_instruction == ai_coach.SYSTEM_INSTRUCTIONS
    assert second[-1]["content"] == "Respuesta 2"


def test_gradio6_accepts_shared_send_and_enter_event_chain():
    import gradio as gr

    with gr.Blocks() as demo:
        model_history = gr.State(value=[])
        pending = gr.State(value="")
        chatbot = gr.Chatbot(layout="bubble")
        question = gr.Textbox()
        send = gr.Button("Enviar")
        clear = gr.Button("Limpiar")
        status = gr.Markdown()
        gr.on(
            triggers=[send.click, question.submit],
            fn=lambda q, h: (h, h, q, gr.update(value="", interactive=False),
                              gr.update(interactive=False), gr.update(interactive=False)),
            inputs=[question, model_history],
            outputs=[model_history, chatbot, pending, question, send, clear],
            trigger_mode="once", concurrency_limit=1,
            concurrency_id="hj-fitness-chat-turn", api_name=False,
        ).success(
            fn=lambda h, q: (h, h, "", q, gr.update(interactive=True),
                              gr.update(interactive=True), gr.update(interactive=True)),
            inputs=[model_history, pending],
            outputs=[model_history, chatbot, status, pending, question, send, clear],
            concurrency_limit=1, concurrency_id="hj-fitness-chat-turn",
            api_name=False,
        )
    assert demo is not None
