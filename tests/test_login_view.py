"""Regression checks for the password-login welcome copy.

These tests need neither a database connection nor the Gradio runtime.
"""
from html.parser import HTMLParser

from inbody_mvp.login_view import LOGIN_AUTH_MESSAGE


class _LoginMarkupParser(HTMLParser):
    def error(self, message):
        raise AssertionError(message)


def test_login_describes_current_and_planned_features():
    copy = LOGIN_AUTH_MESSAGE.lower()
    assert "asistente virtual de fitness" in copy
    assert "registros de entrenamiento" in copy
    assert "inbody" in copy
    assert "dieta" in copy
    assert "exámenes médicos" in copy
    assert "chat" in copy
    assert "priorizar acciones" in copy
    assert "disponible hoy" in copy
    assert "en desarrollo" in copy


def test_login_content_is_scoped_static_html():
    copy = LOGIN_AUTH_MESSAGE.lower()
    parser = _LoginMarkupParser()
    parser.feed(LOGIN_AUTH_MESSAGE)
    parser.close()

    assert '<section' in copy
    assert 'max-width:100%' in copy
    assert 'grid-template-columns:repeat(auto-fit' in copy
    assert '<script' not in copy
    assert '<form' not in copy
    assert '<input' not in copy
