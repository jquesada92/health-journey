"""Academic module-one deliverable editor and local DOCX export.

Based on "Actividad Sesión 4 · Actividad principal" (Fundamentos de la
Programación): eight ordered sections, four screenshots and a five-sentence
pitch. The course HTML describes the structure, not the original Blackboard
Word template, which was not supplied.

This module never accesses Neon/Gemini; draft fields remain Gradio-session-only.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Mapping, Sequence

TITLE = "Health Journey — Asistente de IA para composición corporal y entrenamiento"
COURSE = "Fundamentos de la Programación"
ACTIVITY = "Actividad principal · Sesión 4"
DEADLINE = "02/11/2026"
SECTION_ORDER = (
    ("enlaces", "1. Enlaces"),
    ("problema", "2. Problema y usuario"),
    ("especificacion", "3. Especificación"),
    ("pieza_ia", "4. La pieza de IA"),
    ("proceso_ia", "5. Proceso con IA"),
    ("prueba_mejora", "6. Prueba y mejora"),
    ("pitch", "7. Pitch escrito"),
    ("capturas", "8. Capturas"),
)
RUBRIC = (
    ("Problema y usuario", 10),
    ("Especificación y prompting", 10),
    ("App desplegada y funcional", 25),
    ("Integración de la IA", 20),
    ("Proceso con IA y harness", 15),
    ("Prueba y mejora", 10),
    ("README y pitch escrito", 10),
)
DEFAULT_CONTENT: dict[str, str] = {
    "enlaces": (
        "Aplicación desplegada (Hugging Face Spaces): "
        "https://huggingface.co/spaces/jaqo/health-journey\n"
        "Repositorio de código y documentación: "
        "https://github.com/jquesada92/health-journey\n"
        "Archivos de entrega técnica: app.py, requirements.txt, README.md "
        "y AGENTS.md. Antes de enviar a Blackboard, comprobar que el Space "
        "carga correctamente en ventana de incógnito."
    ),
    "problema": (
        "El usuario objetivo es una persona que entrena y necesita observar "
        "cómo evolucionan su composición corporal y su rendimiento.\n\n"
        "Actualmente los resultados InBody se reciben en PDF o imágenes "
        "de equipos distintos y los entrenamientos se registran en "
        "FitNotes. Comparar fechas, unidades y medidas exige transcribir "
        "datos manualmente y consultar sistemas separados.\n\n"
        "Health Journey centraliza los exámenes y series de entrenamiento, "
        "conserva su historial y ofrece gráficas de progreso. Gemini "
        "interpreta las imágenes o PDF para proponer mediciones estructuradas "
        "y utiliza resúmenes autorizados para responder preguntas de fitness. "
        "La persona revisa los valores antes de guardarlos; la IA no "
        "diagnostica enfermedades ni sustituye profesionales sanitarios."
    ),
    "especificacion": (
        "Entradas: PDF/JPG/PNG de InBody; exportaciones CSV de FitNotes; "
        "preguntas de texto, objetivos y período de análisis.\n\n"
        "Funciones: comprobar duplicados antes de la extracción; seleccionar "
        "un modelo Gemini disponible; extraer fecha, medidas y unidades; "
        "revisar el documento original junto a una tabla; corregir valores "
        "sin perder el original; marcar reviewed y guardar con un solo "
        "botón; cargar series FitNotes; consultar tendencias y usar el chat.\n\n"
        "Salidas: mediciones normalizadas y auditadas en PostgreSQL (Neon), "
        "tablas de entrenamiento, gráficas de evolución y respuestas "
        "conversacionales condicionadas a los datos disponibles.\n\n"
        "Criterios de aceptación: no enviar documentos a IA sin consentimiento; "
        "rechazar archivos no admitidos o duplicados confirmados; conservar "
        "decimales y negativos; no guardar filas sin revisión; no escribir "
        "ante errores de validación; separar permiso de extracción, "
        "almacenamiento y chat; mostrar errores comprensibles en móvil."
    ),
    "pieza_ia": (
        "Se utiliza la API de Google Gemini Flash, integrada desde Python "
        "mediante google-genai, con prompts separados para extracción InBody "
        "y asesoramiento fitness. El modelo multimodal permite interpretar "
        "documentos que varían entre máquinas y presentar campos "
        "estructurados; el chat relaciona tendencias InBody y FitNotes.\n\n"
        "Se eligió una API alojada para evitar depender de una GPU local. "
        "Si se produce un error de API, cuota, red o respuesta no válida, "
        "la aplicación debe informar al usuario sin inventar mediciones "
        "ni registrar resultados incompletos. Los permisos se comprueban "
        "antes de cada envío, y las claves viven en secretos del servidor. "
        "El análisis de entrenamiento no es una valoración clínica."
    ),
    "proceso_ia": (
        "La especificación y las decisiones técnicas se documentan en "
        "AGENTS.md, harness/ y archivos de soporte del repositorio. "
        "Los prompts versionados del extractor y del chat se encuentran "
        "en inbody_mvp/prompts/inbody_extraction.md y "
        "inbody_mvp/prompts/fitness_coach.md.\n\n"
        "Se utilizó asistencia de IA para propuestas de arquitectura, "
        "edición de código, pruebas sintéticas y revisión documental. "
        "Se comprobaron manualmente requisitos, datos extraídos, privacidad, "
        "trazabilidad de correcciones y fallos de CI antes de integrar "
        "cambios. GitHub Actions ejecuta pruebas automatizadas y validación "
        "del harness. No debe afirmarse que una prueba sintética equivale "
        "a validación de extremo a extremo en producción."
    ),
    "prueba_mejora": (
        "Prueba documentada: revisión del flujo InBody durante el desarrollo "
        "por parte del propio autor como usuario. Se detectó que los pasos "
        "de revisar y validar y los botones de guardar cambios y guardar "
        "mediciones resultaban redundantes. Se sustituyeron por una "
        "revisión de la tabla con indicador reviewed y un solo botón "
        "de persistencia, conservando la validación en el backend.\n\n"
        "También se corrigieron pruebas de autorización y se incorporaron "
        "casos para valores negativos, precisión decimal, duplicados y "
        "conservación del formulario cuando falla el guardado.\n\n"
        "Evidencia pendiente de completar por el autor: resultado de una "
        "prueba funcional con capturas, fecha de prueba, URL realmente "
        "accesible en incógnito y, si existe, prueba cruzada con un compañero "
        "y feedback dejado en el debate del curso."
    ),
    "pitch": (
        "Los resultados InBody y los entrenamientos suelen estar dispersos, "
        "lo que dificulta seguir el progreso físico.\n"
        "Health Journey reúne ambos historiales en una aplicación web "
        "para revisar medidas y analizar tendencias.\n"
        "Gemini ayuda a extraer datos de reportes variables y responder "
        "preguntas utilizando solo la información autorizada.\n"
        "Las pruebas de revisión permitieron simplificar el proceso a "
        "una tabla verificable y un único botón de guardado.\n"
        "El siguiente paso es reforzar la validación de extremo a extremo "
        "y ampliar el seguimiento con nuevos registros de salud."
    ),
    "capturas": (
        "Adjuntar cuatro capturas reales, cada una con una línea explicativa: "
        "aplicación funcionando; caso límite o error; momento de trabajo "
        "con IA; prueba de usuario. No insertar capturas ficticias."
    ),
}
DEFAULT_CAPTIONS = (
    "Aplicación funcionando: formulario InBody con tabla de revisión y visor original.",
    "Caso límite o error: mensaje controlado ante duplicado o archivo no válido.",
    "Trabajo con IA: prompt versionado o PR con revisión de los cambios generados.",
    "Prueba: ejecución documentada de la app o de un caso de validación.",
)
DEFAULT_CAPTIONS_TEXT = "\n".join(DEFAULT_CAPTIONS)


def _clean(text: object, limit: int = 16000) -> str:
    return str(text if text is not None else "").strip()[:limit]


def as_submission(title: str, author: str, *texts: str) -> dict:
    """Eight section texts plus newline-separated screenshot captions."""
    if len(texts) != 9:
        raise ValueError("Se requieren ocho apartados y cuatro pies de captura.")
    sections = {
        key: _clean(raw)
        for (key, _), raw in zip(SECTION_ORDER, texts[:8], strict=True)
    }
    captions = [_clean(x, 250) for x in _clean(texts[8], 2500).splitlines()]
    captions = (captions + [""] * 4)[:4]
    return {
        "title": _clean(title, 180) or TITLE,
        "author": _clean(author, 120) or "[Autor pendiente de completar]",
        "sections": sections,
        "captions": captions,
    }


def render_submission_preview(title: str, author: str, *texts: str) -> str:
    data = as_submission(title, author, *texts)
    lines = [
        f"# {data['title']}",
        f"**{COURSE} · {ACTIVITY}**",
        f"**Autor:** {data['author']}  ",
        f"**Cierre de la actividad:** {DEADLINE}",
        "",
        "> Borrador editable. La estructura proviene de la actividad oficial; "
        "la plantilla visual de Blackboard no se adjuntó.",
    ]
    for key, label in SECTION_ORDER:
        lines.extend(["", f"## {label}", "", data["sections"][key] or "[Pendiente]"])
        if key == "capturas":
            lines.append("")
            for index, caption in enumerate(data["captions"], start=1):
                lines.append(f"- Captura {index}: {caption or '[Pie pendiente]'}")
    return "\n".join(lines)


def _add_paragraphs(document, text: str) -> None:
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            document.add_paragraph("")
        elif stripped.startswith(("- ", "• ")):
            document.add_paragraph(stripped[2:], style="List Bullet")
        else:
            document.add_paragraph(stripped)


def generate_submission_docx(
    title: str, author: str, *texts_and_images: object
) -> str:
    """Return a temporary Word path for gr.File; screenshots are optional.

    The output is explicitly labeled a draft until four evidence images
    are attached. Images never go to Gemini or Neon.
    """
    if len(texts_and_images) != 10:
        raise ValueError("Faltan campos del entregable.")
    images = texts_and_images[-1] or []
    if isinstance(images, (str, Path)):
        images = [images]
    if len(images) > 4:
        raise ValueError("La actividad solicita exactamente cuatro capturas como máximo.")
    data = as_submission(title, author, *texts_and_images[:9])
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("No está instalada la dependencia python-docx o Pillow.") from exc

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)
    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    for style_name in ("Title", "Heading 1", "Heading 2"):
        document.styles[style_name].font.name = "Aptos Display"
        document.styles[style_name].font.color.rgb = RGBColor(30, 58, 93)

    document.add_heading(data["title"], 0)
    meta = document.add_paragraph(f"{COURSE} · {ACTIVITY}")
    meta.style = "Subtitle"
    document.add_paragraph(f"Autor: {data['author']}")
    document.add_paragraph(f"Fecha límite indicada en la actividad: {DEADLINE}")
    document.add_paragraph(
        "Documento académico preparado con la estructura de ocho apartados "
        "indicada en las instrucciones de la actividad. "
        "Verificar enlaces, pruebas y capturas antes de entregar."
    )
    for key, label in SECTION_ORDER:
        document.add_heading(label, level=1)
        _add_paragraphs(document, data["sections"][key])
        if key != "capturas":
            continue
        for index in range(4):
            document.add_heading(f"Captura {index + 1}", level=2)
            if index < len(images):
                path = Path(str(images[index]))
                if not path.is_file() or path.suffix.lower() not in {
                    ".png", ".jpg", ".jpeg",
                } or path.stat().st_size > 8 * 1024 * 1024:
                    raise ValueError("Captura no válida: utiliza PNG/JPG de hasta 8 MB.")
                with Image.open(path) as im:
                    im.verify()
                with Image.open(path) as im:
                    width_px, height_px = im.size
                width_in = min(6.15, 7.1 * width_px / max(height_px, 1))
                document.add_picture(str(path), width=Inches(width_in))
                document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                document.add_paragraph("[Captura pendiente de adjuntar]")
            document.add_paragraph(
                data["captions"][index] or "[Descripción de captura pendiente]"
            )
    footer = section.footer.paragraphs[0]
    footer.text = "Health Journey · Fundamentos de la Programación · Módulo 1"
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    with NamedTemporaryFile(prefix="health-journey-modulo1-", suffix=".docx",
                            delete=False) as output:
        target = output.name
    document.save(target)
    return target
