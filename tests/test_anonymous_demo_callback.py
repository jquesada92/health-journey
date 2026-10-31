"""Exercise the real Gradio save callback without starting OCR or Neon."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]


def callback_environment(demo=True, ready=True):
    calls = []
    source = (ROOT / "app.py").read_text()
    tree = ast.parse(source)
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "save_reviewed"
    ]
    assert len(matches) == 1
    fn = matches[0]
    # Defer annotation evaluation so imported Gradio does not need to run.
    fn.decorator_list = []
    fn.returns = None
    for arg in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]:
        arg.annotation = None
    namespace = {
        "gr": SimpleNamespace(Error=ValueError),
        "uuid4": uuid4,
        "anonymous_demo_requested": lambda: demo,
        "anonymous_demo_enabled": lambda: ready,
        "prepare_confirmed_exam": lambda *args: (
            calls.append(("prepared", args)),
            SimpleNamespace(id_persona=args[2]),
        )[1],
        "save_demo_exam": lambda *args, **kwargs: (
            calls.append(("demo", kwargs)),
            "example",
        )[1],
        "require_database_access": lambda profile: calls.append(("private_auth", profile)),
        "save_confirmed_exam": lambda *args, **kwargs: (
            calls.append(("private_save", kwargs)),
            "example",
        )[1],
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<save_reviewed>", "exec"), namespace)
    return namespace["save_reviewed"], calls


def args(consent=True, publish=True):
    return (
        {"synthetic": True}, [], "REAL-ID-MUST-NOT-SAVE", "InBody 580",
        "2026-10-31T10:00:00", 35, "ES", publish, consent, str(uuid4()),
    )


def test_demo_without_consent_is_rejected_before_any_database_action():
    fn, calls = callback_environment()
    with pytest.raises(ValueError, match="aceptar el almacenamiento"):
        fn(*args(consent=False))
    assert calls == []


def test_demo_uses_anonymous_id_no_auth_and_separate_publish_choice():
    fn, calls = callback_environment()
    msg = fn(*args(consent=True, publish=False))
    assert "sin publicación" in msg
    assert [kind for kind, _ in calls] == ["prepared", "demo"]
    assert calls[0][1][2].startswith("ANON-")
    assert calls[0][1][2] != "REAL-ID-MUST-NOT-SAVE"
    assert calls[0][1][5] is None
    assert calls[1][1]["storage_consent"] is True
    assert calls[1][1]["publish_consent"] is False


def test_non_demo_still_uses_original_private_auth_guard():
    fn, calls = callback_environment(demo=False)
    fn(*args(consent=True, publish=False), profile=None)
    assert [kind for kind, _ in calls] == [
        "private_auth", "prepared", "private_save"
    ]
