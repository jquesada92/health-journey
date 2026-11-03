"""Pure, session-only chat turns for a predictable messaging interface.

Gradio Chatbot is a rendered view; this module maintains a separate
session-scoped canonical message list. Never persists messages to Neon.
"""
from __future__ import annotations

MAX_VISIBLE_MESSAGES = 160
MAX_MESSAGE_CHARS = 1500
MAX_ASSISTANT_CHARS = 6500


def clean_chat_messages(messages) -> list[dict]:
    """Accept only role/text pairs and copy them to prevent state aliasing."""
    cleaned = []
    if not isinstance(messages, list):
        return cleaned
    for entry in messages[-MAX_VISIBLE_MESSAGES:]:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        if content.strip():
            cleaned.append({"role": role, "content": content[:MAX_ASSISTANT_CHARS]})
    return cleaned


def enqueue_user_message(question, messages) -> tuple[list[dict], str]:
    """Append the user bubble before making any Gemini API request."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Escribe un mensaje para el asistente.")
    message = question.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError("El mensaje supera el límite de 1500 caracteres.")
    history = clean_chat_messages(messages)
    if history and history[-1]["role"] == "user":
        raise ValueError("Todavía se está procesando tu mensaje anterior.")
    history.append({"role": "user", "content": message})
    return history[-MAX_VISIBLE_MESSAGES:], message


def append_assistant_message(messages, reply: str) -> list[dict]:
    """Finish an outstanding turn without discarding earlier visible bubbles."""
    history = clean_chat_messages(messages)
    if not history or history[-1]["role"] != "user":
        raise ValueError("No hay una pregunta pendiente para responder.")
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("No se recibió ninguna respuesta del asistente.")
    history.append({"role": "assistant", "content": reply.strip()[:MAX_ASSISTANT_CHARS]})
    return history[-MAX_VISIBLE_MESSAGES:]
