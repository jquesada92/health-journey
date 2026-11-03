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
    "harness/00_estado_vigente_y_trazabilidad.md",
    "harness/10_continuidad_noviembre_2026.md",
    "harness/11_cobertura_codigo_main.md",
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



def comprobar_estado_actual() -> list[str]:
    """Audit source/docs coherence without runtime imports or external credentials."""
    errores = []
    canonical = "harness/00_estado_vigente_y_trazabilidad.md"
    index = "docs/indice_actual.md"
    for required in (canonical, index):
        if not (ROOT / required).is_file():
            errores.append(f"Falta documentación actual: {required}")
    if errores:
        return errores

    snapshot = contenido(canonical)
    for family, maximum in (("F", 15), ("AC-V", 12)):
        found = {
            int(value) for value in re.findall(
                rf"(?m)^\|\s*{family}-(\d{{2}})\s*\|", snapshot
            )
        }
        if found != set(range(1, maximum + 1)):
            errores.append(
                f"Inventario {family}: hay {sorted(found)}, "
                f"se requieren {list(range(1, maximum + 1))}."
            )
    for token in (
        "Gradio", "Gemini", "FitNotes", "Neon", "SQLAlchemy", "psycopg",
        "Pydantic", "PyMuPDF", "Plotly", "Hugging Face", "GitHub",
        "consentimientos", "E2E", "multiturno", "LEGACY", "PENDIENTE",
    ):
        if token not in snapshot:
            errores.append(f"Falta tecnología/estado en {canonical}: {token}")

    app = contenido("app.py")
    for token in (
        'nav_project = gr.Button("Proyecto"',
        'nav_inbody = gr.Button("Extractor de InBody"',
        'nav_training = gr.Button("Captador de logs de entrenamiento"',
        'nav_coach = gr.Button("Chat con el asistente fitness"',
        'with gr.Column(visible=True, elem_id="hj-panel-project")',
        'elem_id="hj-inbody-fixedbar"',
        'session_ai_consent = gr.State(value=False)',
        'session_db_consent = gr.State(value=False)',
        'session_coach_consent = gr.State(value=False)',
        "fn=restore_session_consents",
        "gr.Chatbot(",
    ):
        if token not in app:
            errores.append(f"Contrato UI actual ausente en app.py: {token}")

    if 'session_ai_consent = gr.Checkbox(' in app:
        errores.append("Consentimientos duplicados: extracción en app.py.")
    if 'session_db_consent = gr.Checkbox(' in app:
        errores.append("Consentimientos duplicados: almacenamiento en app.py.")
    if 'session_coach_consent = gr.Checkbox(' in app:
        errores.append("Consentimientos duplicados: chat en app.py.")

    for path, required_tokens in {
        "inbody_mvp/prelogin_consent.py": (
            'name="ai_consent"', 'name="db_consent"', 'name="coach_consent"',
            "has_consent", "PrivacyFirstMiddleware",
        ),
        "inbody_mvp/gemini_review.py": (
            "def extract_gemini(", "def save_audit(", "PROMPT",
            "validate_review",
        ),
        "inbody_mvp/training_hub.py": (
            "def parse_fitnotes_bytes(", "def save_training_import(",
            "def _owner_key(",
        ),
        "inbody_mvp/ai_coach.py": (
            "def answer_coach_question(", "def load_coach_context(",
            "has_consent",
        ),
        "inbody_mvp/inbody_flow.py": (
            "position: fixed !important;", "def render_inbody_flow(",
            "INBODY_NEXT_STEP_JS",
        ),
        ".github/workflows/test-inbody.yml": (
            "ruff check --select F821", "compileall", "pytest -q",
            "test_ai_coach.py", "test_training_hub.py",
        ),
        ".github/workflows/deploy-huggingface.yml": (
            "inbody_mvp/ai_coach.py", "inbody_mvp/training_hub.py",
            "inbody_mvp/prelogin_consent.py", "HF_SPACE_ID", "HF_TOKEN",
        ),
        "requirements.txt": (
            "gradio[oauth]>=6.0,<7.0", "google-genai",
            "SQLAlchemy", "psycopg", "PyMuPDF", "plotly", "pydantic",
        ),
    }.items():
        source = contenido(path)
        for token in required_tokens:
            if token not in source:
                errores.append(f"Contrato fuente en {path} no encontrado: {token}")

    for migration in (
        "004_gemini_measurement_audit.sql",
        "005_consent_only_audit_writer.sql",
        "006_app_master_demo_account.sql",
        "007_idempotent_audit_save.sql",
        "008_fitnotes_training_hub.sql",
    ):
        if not (ROOT / "migrations" / migration).is_file():
            errores.append(f"Falta migración versionada: {migration}")

    guide_files = [
        "README.md", "AGENTS.md", "harness/README.md",
        "harness/PROMPT_AGENTE.md",
        *(
            f"harness/{name}.md" for name in (
                "01_producto_y_alcance", "02_arquitectura_y_flujos",
                "03_modelo_de_datos_y_csv", "04_extraccion_y_normalizacion",
                "05_interfaz_y_dashboard", "06_seguridad_y_privacidad",
                "07_reconstruccion_y_operacion", "08_pruebas_y_criterios",
                "09_estado_y_decisiones", "10_continuidad_noviembre_2026",
            )
        ),
    ]
    for item in guide_files:
        source = contenido(item)
        if "2026-11-03" not in source:
            errores.append(f"Falta revisión con fecha en {item}")

    index_content = contenido(index)
    for item in (
        "ai-coach.md", "training-hub.md", "neon-postgres.md",
        "despliegue-hugging-face.md", "gemini-measurement-audit.md",
        "dashboard-publico.md", "demo-anonima-consentimiento.md",
        "inbody-layouts.md", "ocr-secciones-ia.md",
    ):
        if item not in index_content:
            errores.append(f"Índice documental incompleto: {item}")

    # Prompts are already merged in main. Keep each non-Python prompt
    # asset explicit in the deployment allowlist.
    prompt_dir = ROOT / "inbody_mvp" / "prompts"
    if prompt_dir.exists():
        deployment = contenido(".github/workflows/deploy-huggingface.yml")
        for filename in ("inbody_extraction.md", "fitness_coach.md"):
            if not (prompt_dir / filename).is_file():
                errores.append(f"Falta prompt por módulo: {filename}")
            if f"inbody_mvp/prompts/{filename}" not in deployment:
                errores.append(f"Deploy no incluye prompt: {filename}")
    return errores


def comprobar_cobertura_documental() -> list[str]:
    """Require inventory references for every versioned product artifact.

    Does not read personal files or .env, never accesses Neon/Hugging Face.
    Diff-aware in CI: a newly added module/test/migration/doc must be
    documented with its complete relative path in the inventory.
    """
    errores = []
    manifest_path = "harness/11_cobertura_codigo_main.md"
    if not (ROOT / manifest_path).is_file():
        return [f"Falta inventario de main: {manifest_path}"]
    manifest = contenido(manifest_path)
    product_files = [ROOT / "app.py"]
    for folder, glob in (
        ("inbody_mvp", "**/*.py"),
        ("inbody_mvp/prompts", "*.md"),
        ("migrations", "*.sql"),
        ("db", "**/*.sql"),
        ("sql", "**/*.sql"),
        ("docs", "*.md"),
        ("tests", "test_*.py"),
        (".github/workflows", "*.yml"),
    ):
        root = ROOT / folder
        if root.is_dir():
            product_files.extend(root.glob(glob))
    for path in (
        ".env.example", ".gitattributes", ".gitignore", "AGENTS.md",
        "README.md", "especificacion.md", "requirements.txt",
        "requirements-ai.txt", "run_local.sh", "run_local_ai.sh",
    ):
        if (ROOT / path).is_file():
            product_files.append(ROOT / path)
    for file in product_files:
        if not file.is_file():
            continue
        rel = file.relative_to(ROOT).as_posix()
        if "`" + rel + "`" not in manifest:
            errores.append(
                f"Artefacto de main sin documentación literal en {manifest_path}: {rel}"
            )

    # Enforce the merged user experience, not the obsolete 5-step wording
    # that is preserved in legacy/historical sections.
    flow = contenido("inbody_mvp/inbody_flow.py")
    app = contenido("app.py")
    if 'STEPS = ("Cargar", "Extraer", "Revisar", "Guardar")' not in flow:
        errores.append("Barra de progreso divergente: se requieren cuatro pasos.")
    if "gemini_check.click(" in app or "progress_after_validation" in app:
        errores.append("No reintroducir la etapa Validar/Guardar cambios.")
    if app.count("gemini_save.click(") != 1:
        errores.append("Se requiere un único evento Guardar mediciones.")
    if '"Guardar mediciones"' not in app or "review_step_ready(" not in app:
        errores.append("La confirmación reviewed + guardar no está conectada.")
    if "reconcile_native_review_rows(table, snapshot)" not in app:
        errores.append("El guardado debe reconciliar la tabla antes de escribir.")
    if "fn=restore_session_consents" not in app:
        errores.append("Permisos previos al login no se restauran.")
    for token in (
        "load_private_training_sets", "resolve_private_person_id",
    ):
        if token not in contenido("inbody_mvp/coach_data.py"):
            errores.append(f"Falta contexto privado del coach: {token}")

    if (ROOT / "inbody_mvp/semantic_metadata.py").exists():
        for rel in (
            "inbody_mvp/semantic_metadata.py",
            "migrations/009_ai_semantic_metadata.sql",
            "tests/test_semantic_metadata.py",
        ):
            if not (ROOT / rel).is_file():
                errores.append(f"Falta artefacto semántico del PR: {rel}")
        loader = contenido("inbody_mvp/semantic_metadata.py")
        coach = contenido("inbody_mvp/ai_coach.py")
        deploy = contenido(".github/workflows/deploy-huggingface.yml")
        if "def load_coach_semantics(" not in loader:
            errores.append("Falta loader de definiciones semánticas.")
        if '"semantic_metadata": semantics' not in coach:
            errores.append("El chat no incluye el catálogo en su contexto.")
        if "'inbody_mvp/semantic_metadata.py'" not in deploy:
            errores.append("El deploy HF omite semantic_metadata.py.")
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
    # Solo módulos efectivamente requeridos por el flujo de ejecución actual.
    # section_ai.py es importado por extractor.py durante startup aunque
    # el análisis OCR con Paddle esté desactivado; sin este módulo falla Space.
    # Los módulos legacy de OCR/editor se conservan para pruebas antiguas,
    # pero no deben formar parte del paquete activo en Hugging Face.
    activos = ['inbody_mvp/__init__.py','inbody_mvp/extractor.py','inbody_mvp/layouts.py','inbody_mvp/layouts_es.py','inbody_mvp/gemini_review.py','inbody_mvp/review.py','inbody_mvp/language.py','inbody_mvp/storage.py','inbody_mvp/public_dashboard.py','inbody_mvp/oauth_ui.py','inbody_mvp/demo_storage.py','inbody_mvp/progress_dashboard.py','inbody_mvp/app_auth.py','inbody_mvp/section_ai.py']
    obsoletos = ["inbody_mvp/visual_debug.py", "inbody_mvp/section_review.py",
                 "inbody_mvp/visual_editor.py", "inbody_mvp/visual_editor_ui.py",
                 ]
    for rel in activos:
        if rel not in workflow:
            errores.append(f"Falta módulo activo en despliegue: {rel}")
    for rel in obsoletos:
        if f"\x27{rel}\x27" in workflow:
            errores.append(f"Módulo obsoleto incluido en despliegue: {rel}")

    errores.extend(comprobar_documentacion())
    errores.extend(comprobar_estado_actual())
    errores.extend(comprobar_cobertura_documental())

    print("Estado de servicios: no consultados por este verificador.")
    for key in ("DATABASE_URL", "ENABLE_PERSISTENCE", "HF_ALLOWED_USERS"):
        print(f"Entorno {key}: {'definida' if key in os.environ else 'no definida'}")
    print("Nunca se muestran valores de secretos.")

    objetivos = {
        "Exportación CSV existente": "export_draft_csv" in review,
        "Guardar auditoría Gemini en Neon (código)": "save_audit" in app,
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
    print("APROBADO: inventario completo de archivos main, contratos UI, DDL, test, CI y documentación auditados.")
    print("Nota: comprobación estática, no certifica requisitos pendientes ni E2E.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
