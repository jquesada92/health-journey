"""Pruebas estáticas mínimas del montaje de la interfaz Gradio.

Evitan el NameError de publication_choice que pasó las pruebas OCR,
porque antes CI solo compilaba app.py, sin validar referencias usadas
durante la construcción de gr.Blocks. No cargan modelos ni datos reales.
"""
from __future__ import annotations

import ast
from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "app.py"


def _tree():
    return ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))


def _is_widget(call, widget):
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "gr"
        and call.func.attr == widget
    )


def test_publication_checkbox_is_defined_before_it_is_used():
    tree = _tree()
    defined = [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "publication_choice"
            for target in node.targets
        )
    ]
    assert len(defined) == 1, "Falta o se duplicó la casilla de publicación."
    lineno, call = defined[0]
    assert _is_widget(call, "Checkbox")
    default = next((k.value for k in call.keywords if k.arg == "value"), None)
    assert isinstance(default, ast.Constant) and default.value is False

    refs = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id == "publication_choice"
        and isinstance(node.ctx, ast.Load)
    ]
    assert refs, "Debe conectarse la casilla con Guardar y Limpiar."
    assert all(line > lineno for line in refs), (
        "La casilla debe crearse antes de referenciarla en Gradio."
    )


def test_publication_checkbox_is_read_for_save_and_reset_by_clear():
    tree = _tree()
    interactions = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("click", "ClearButton")
    ]
    assert any(
        n.func.attr == "click"
        and any(
            keyword.arg == "inputs"
            and isinstance(keyword.value, ast.List)
            and any(
                isinstance(x, ast.Name) and x.id == "publication_choice"
                for x in keyword.value.elts
            )
            for keyword in n.keywords
        )
        for n in interactions
    ), "Guardar debe recibir la decisión explícita de publicación."

    assert any(
        _is_widget(n, "ClearButton")
        and any(
            isinstance(a, ast.List)
            and any(
                isinstance(x, ast.Name) and x.id == "publication_choice"
                for x in a.elts
            )
            for a in n.args
        )
        for n in interactions
    ), "Limpiar debe restablecer la casilla, evitando publicaciones involuntarias."
