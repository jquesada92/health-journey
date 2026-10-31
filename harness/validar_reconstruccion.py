#!/usr/bin/env python3
"""Comprobación offline y sin secretos de la reconstrucción de Health Journey.

Verifica estructura y contratos mínimos existentes; los requisitos todavía
pendientes se reportan como PENDIENTE en lugar de fingir implementación.
No conecta a Neon/HF, no abre .env ni inspecciona datos personales.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "harness"

ARCHIVOS_OBLIGATORIOS = (
    "README.md",
    "AGENTS.md",
    "especificacion.md",
    "requirements.txt",
    "app.py",
    "inbody_mvp/__init__.py",
    "inbody_mvp/extractor.py",
    "inbody_mvp/layouts.py",
    "inbody_mvp/layouts_es.py",
    "inbody_mvp/language.py",
    "inbody_mvp/review.py",
    "inbody_mvp/storage.py",
    "db/schema.sql",
    ".github/workflows/deploy-huggingface.yml",
    ".github/workflows/test-inbody.yml",
    "harness/README.md",
    *(
        f"harness/{name}.md" for name in (
            "01_producto_y_alcance",
            "02_arquitectura_y_flujos",
            "03_modelo_de_datos_y_csv",
            "04_extraccion_y_normalizacion",
            "05_interfaz_y_dashboard",
            "06_seguridad_y_privacidad",
            "07_reconstruccion_y_operacion",
            "08_pruebas_y_criterios",
            "09_estado_y_decisiones",
        )
    ),
    "harness/PROMPT_AGENTE.md",
)

CONTRATO_CSV = [
    "id_persona",
    "modelo_inbody",
    "timestamp",
    "variable_medida",
    "unidad_medida",
    "valor_medida",
    "edad",
]

OBJETOS_SQL = (
    "hj_persons",
    "hj_exams",
    "hj_measurements",
    "hj_measurement_catalog",
    "hj_measurements_long",
)


def contenido(ruta: str) -> str:
    return (ROOT / ruta).read_text(encoding="utf-8")


def contrato_exportacion(texto: str) -> list[str] | None:
    """Extrae EXPORT_COLUMNS mediante AST sin importar dependencias."""
    try:
        tree = ast.parse(texto)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "EXPORT_COLUMNS":
                        value = ast.literal_eval(node.value)
                        return value if isinstance(value, list) else None
    except (SyntaxError, ValueError):
        return None
    return None


def comprobar_documentacion() -> list[str]:
    errores = []
    texto = contenido("harness/08_pruebas_y_criterios.md")
    for nombre, maximo in (("CA", 36), ("CS", 10)):
        encontrados = {
            int(x) for x in re.findall(rf"\|\s*{nombre}-(\d+)\s*\|", texto)
        }
        previstos = set(range(1, maximo + 1))
        if encontrados != previstos:
            errores.append(
                f"Criterios {nombre}: encontrados {sorted(encontrados)}, "
                f"esperados {sorted(previstos)}."
            )
    return errores


def main() -> int:
    errores = []
    print("Health Journey — verificador de reconstrucción (sin servicios externos)")
    for ruta in ARCHIVOS_OBLIGATORIOS:
        if not (ROOT / ruta).is_file():
            errores.append(f"Falta archivo obligatorio: {ruta}")
    if errores:
        for mensaje in errores:
            print("FALLIDO:", mensaje)
        return 1

    readme = contenido("README.md")
    if "sdk: gradio" not in readme or "app_file: app.py" not in readme:
        errores.append("README.md debe definir sdk: gradio y app_file: app.py.")

    app = contenido("app.py")
    if "import gradio as gr" not in app or "gr.Blocks(" not in app:
        errores.append("No se encontró la interfaz Gradio requerida.")
    if re.search(r"(?m)^\s*(?:import\s+dash\b|from\s+dash\b)", app):
        errores.append("Dash no puede usarse como UI en el MVP.")

    review = contenido("inbody_mvp/review.py")
    if contrato_exportacion(review) != CONTRATO_CSV:
        errores.append("EXPORT_COLUMNS no cumple contrato de siete columnas.")

    schema = contenido("db/schema.sql").lower()
    for objeto in OBJETOS_SQL:
        if objeto.lower() not in schema:
            errores.append(f"Falta objeto SQL en db/schema.sql: {objeto}")

    workflow = contenido(".github/workflows/deploy-huggingface.yml")
    for module in sorted((ROOT / "inbody_mvp").glob("*.py")):
        rel = module.relative_to(ROOT).as_posix()
        if rel not in workflow:
            errores.append(f"El workflow no incluye el módulo de ejecución: {rel}")

    errores.extend(comprobar_documentacion())

    print("Estado de servicios: no consultados por este verificador.")
    for key in ("DATABASE_URL", "ENABLE_PERSISTENCE", "HF_ALLOWED_USERS"):
        print(f"Entorno {key}: {'definida' if key in os.environ else 'no definida'}")
    print("Nunca se muestran valores de secretos.")

    objetivos = {
        "Exportación CSV existente": "export_draft_csv" in review,
        "Guardar en Neon (código)": "save_confirmed_exam" in app,
        "Consultar Neon (código)": "load_measurement_history" in app,
        "CSV con nombre hash+UTC (objetivo)": (
            "sha256" in app.lower() and "export" in app.lower()
            and ("datetime.now" in app or "timezone.utc" in app)
        ),
        "Importación de múltiples CSV (objetivo)": (
            'file_count="multiple"' in app
            or "file_count='multiple'" in app
        ),
    }
    for nombre, disponible in objetivos.items():
        print(f"{'DETECTADO' if disponible else 'PENDIENTE'}: {nombre}")

    if errores:
        for mensaje in errores:
            print("FALLIDO:", mensaje)
        return 1
    print("APROBADO: estructura, contrato CSV, DDL y documentación consistentes.")
    print("Nota: comprobación estática, no certifica requisitos pendientes ni E2E.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
