"""Synthetic module-one academic deliverable tests (no Gemini/Neon)."""
from pathlib import Path

import pytest
from docx import Document
from PIL import Image

from inbody_mvp import module1_deliverable as deliverable

ROOT = Path(__file__).resolve().parents[1]


def _arguments():
    return tuple(
        deliverable.DEFAULT_CONTENT[key]
        for key, _ in deliverable.SECTION_ORDER
    ) + (deliverable.DEFAULT_CAPTIONS_TEXT,)


def test_eight_sections_match_official_activity_order_and_pitch_five_sentences():
    assert [label for _, label in deliverable.SECTION_ORDER] == [
        "1. Enlaces", "2. Problema y usuario", "3. Especificación",
        "4. La pieza de IA", "5. Proceso con IA", "6. Prueba y mejora",
        "7. Pitch escrito", "8. Capturas",
    ]
    assert len(deliverable.DEFAULT_CONTENT["pitch"].splitlines()) == 5
    assert sum(weight for _, weight in deliverable.RUBRIC) == 100
    assert len(deliverable.DEFAULT_CAPTIONS) == 4


def test_preview_and_export_retain_eight_editable_sections_without_making_up_evidence():
    fields = list(_arguments())
    fields[1] = "Texto de problema actualizado por el alumno."
    preview = deliverable.render_submission_preview(
        "Título de ensayo", "Autor de prueba", *fields
    )
    assert "Texto de problema actualizado por el alumno." in preview
    assert "Autor de prueba" in preview
    assert preview.index("## 1. Enlaces") < preview.index("## 8. Capturas")
    assert "plantilla visual de Blackboard no se adjuntó" in preview
    path = Path(deliverable.generate_submission_docx(
        "Título de ensayo", "Autor de prueba", *fields, None,
    ))
    try:
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "Texto de problema actualizado por el alumno." in text
        assert "Autor de prueba" in text
        assert all(label in text for _, label in deliverable.SECTION_ORDER)
        assert text.count("[Captura pendiente de adjuntar]") == 4
        assert text.count("Captura 1") == 1
        assert "https://github.com/jquesada92/health-journey" in text
    finally:
        path.unlink(missing_ok=True)


def test_four_real_image_uploads_are_embedded_and_captioned(tmp_path):
    images = []
    for i in range(4):
        image = tmp_path / f"evidencia_{i}.png"
        Image.new("RGB", (480, 220), color=(255, 255, 255)).save(image)
        images.append(str(image))
    path = Path(deliverable.generate_submission_docx(
        "Módulo uno", "Autora de prueba", *_arguments(), images,
    ))
    try:
        doc = Document(str(path))
        assert len(doc.inline_shapes) == 4
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "[Captura pendiente de adjuntar]" not in text
        assert all(c in text for c in deliverable.DEFAULT_CAPTIONS)
    finally:
        path.unlink(missing_ok=True)


def test_rejects_more_than_four_or_unsupported_images(tmp_path):
    sample = tmp_path / "unsafe.svg"
    sample.write_text("<svg/>")
    with pytest.raises(ValueError, match="máximo"):
        deliverable.generate_submission_docx(
            "Módulo", "Autor", *_arguments(), [str(sample)] * 5,
        )
    with pytest.raises(ValueError, match="Captura no válida"):
        deliverable.generate_submission_docx(
            "Módulo", "Autor", *_arguments(), [str(sample)],
        )


def test_gradio_project_panel_has_functional_docx_download_and_no_external_post():
    app = (ROOT / "app.py").read_text(encoding="utf8")
    assert 'elem_id="hj-module1-deliverables"' in app
    assert '"Generar Word (.docx)"' in app
    assert "fn=render_submission_preview" in app
    assert "fn=generate_module1_word_with_popup" in app
    assert "generate_submission_docx(*values)" in app
    assert "outputs=module1_word_file" in app
    assert "module1_images = gr.File(" in app
    assert "gr.Markdown(PROJECT_OVERVIEW)" in app
    module = (ROOT / "inbody_mvp/module1_deliverable.py").read_text()
    assert "load_coach_context" not in module
    assert "google_genai" not in module
    assert "_database_engine" not in module
    deployment = (ROOT / ".github/workflows/deploy-huggingface.yml").read_text()
    assert "'inbody_mvp/module1_deliverable.py'" in deployment
    requirements = (ROOT / "requirements.txt").read_text()
    assert "python-docx" in requirements
