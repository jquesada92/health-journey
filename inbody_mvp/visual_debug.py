"""Visual diagnostics for actual OCR geometry and optional AI layout boxes.

No inferred measurement-to-box mapping: only detector and OCR evidence is drawn.
The viewer is session-scoped and never persists its debug output to Neon.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .extractor import MAX_UPLOAD_BYTES, DocumentError, validate_file
from .section_ai import ai_detect_layout, ai_sections_requested

COLORS = {"layout": "#2563eb", "ocr": "#ea580c"}
MAX_DEBUG_PAGES = 5


def _pages(filename: str, payload: bytes):
    kind = validate_file(filename, payload)
    if kind == "pdf":
        with fitz.open(stream=payload, filetype="pdf") as document:
            if document.needs_pass:
                raise DocumentError("No se permiten PDFs protegidos por contraseña.")
            for index, page in enumerate(document):
                if index >= MAX_DEBUG_PAGES:
                    break
                pix = page.get_pixmap(dpi=130, colorspace=fitz.csRGB, alpha=False)
                yield index + 1, Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        with Image.open(io.BytesIO(payload)) as src:
            yield 1, ImageOps.exif_transpose(src).convert("RGB").copy()


def _points(raw):
    try:
        if len(raw) != 4:
            return None
        points = [(float(p[0]), float(p[1])) for p in raw]
        return points
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def render_debug(filename: str, payload: bytes, ocr):
    """Return annotated PIL pages, a diagnostic table and an explicit provenance status."""
    if len(payload) > MAX_UPLOAD_BYTES:
        raise DocumentError("Archivo mayor de 15 MB.")
    pictures, rows = [], []
    requested = ai_sections_requested()
    ai_failed = False
    for number, image in _pages(filename, payload):
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        if requested and not ai_failed:
            try:
                detected = ai_detect_layout(image)
            except Exception:
                ai_failed = True
                detected = []
            for reg in detected:
                x0, y0, x1, y1 = reg.box
                draw.rectangle((x0, y0, x1, y1), outline=COLORS["layout"], width=4)
                draw.text((x0, max(0, y0 - 13)), f"IA: {reg.label} ({reg.score:.2f})",
                          fill=COLORS["layout"])
                rows.append([number, "IA layout", reg.label, round(reg.score, 3),
                             str(reg.box), "Región visual; no es una medida"])
        tokens = ocr(image)
        if not isinstance(tokens, list):
            rows.append([number, "OCR", "Sin coordenadas", None, "", "El motor OCR no devolvió cajas"])
        else:
            for token in tokens:
                if not isinstance(token, (tuple, list)) or len(token) < 3:
                    continue
                points = _points(token[0])
                if points is None:
                    continue
                label = str(token[1])
                try:
                    confidence = float(token[2])
                except (ValueError, TypeError):
                    confidence = None
                closed = points + [points[0]]
                draw.line(closed, fill=COLORS["ocr"], width=2)
                rows.append([number, "EasyOCR", label, confidence,
                             str([(round(x), round(y)) for x, y in points]),
                             "Texto detectado; aún sin vinculación validada a una medida"])
        pictures.append(annotated)
    mode = ("Detector IA no disponible en este entorno: se muestran las cajas OCR en naranja. "
            "Para habilitar regiones azules, verifica PaddleOCR/PaddlePaddle y PP-DocLayout-S."
            if ai_failed else "IA de layout activada: azul = regiones del detector; naranja = OCR."
            if requested else
            "IA de layout desactivada: naranja = OCR real. Para ver regiones azules, "
            "instala requirements-ai.txt y activa ENABLE_AI_SECTION_OCR=1 antes de iniciar la app.")
    return pictures, rows, mode
