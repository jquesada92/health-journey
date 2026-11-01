"""Human review of AI-detected document regions before extraction.

Coordinates are absolute pixel coordinates on the 130-DPI preview. Approved
regions are turned into page-relative boxes for the OCR extractor.
No contents are persisted here.
"""
from __future__ import annotations

import hashlib
import io
from PIL import ImageDraw
from .visual_debug import _pages
from .section_ai import ai_detect_layout
from .extractor import DocumentError, MAX_UPLOAD_BYTES

COLUMNS = ["pagina", "seccion", "x0", "y0", "x1", "y1", "incluir", "confianza"]
SECTIONS = {"header", "body_composition", "muscle_fat", "obesity",
            "segmental_lean", "segmental_fat", "research", "impedance",
            "history", "other"}
MAX_REGIONS = 50


def propose_regions(filename: str, data: bytes):
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError("Archivo mayor de 15 MB.")
    images = list(_pages(filename, data))
    rows = []
    used_manual_fallback = False
    for page, image in images:
        # InBody headers are narrow rows, often ignored by generic layout models.
        # Provide a labeled, editable geometry proposal, not a claimed AI detection.
        rows.append([page, "header", 0, 0, image.width, round(image.height * .15), True, None])
        try:
            detected = ai_detect_layout(image)
        except Exception:
            # An unavailable model must not block manual review or the baseline.
            # Do not leak provider exception strings containing local paths.
            detected = []
        if not detected:
            used_manual_fallback = True
            # Editable full lower page proposal, initially NOT included.
            rows.append([page, "other", 0, round(image.height * .15),
                         image.width, image.height, False, None])
        for region in detected:
            x0, y0, x1, y1 = region.box
            rows.append([page, "other", x0, y0, x1, y1, True,
                         round(region.score, 3)])
    if not rows:
        raise DocumentError("No se pudieron generar regiones para revisión.")
    return rows[:MAX_REGIONS], {
        "hash": hashlib.sha256(data).hexdigest(),
        "sizes": {str(page): list(image.size) for page, image in images},
        "layout_mode": "manual" if used_manual_fallback else "paddle",
    }


def validate_regions(table, metadata: dict, data: bytes):
    import pandas as pd
    if not metadata or hashlib.sha256(data).hexdigest() != metadata.get("hash"):
        raise DocumentError("El archivo cambió. Detecta nuevamente sus regiones.")
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table, columns=COLUMNS)
    if list(frame.columns) != COLUMNS:
        raise DocumentError("La tabla de regiones no coincide con el esquema esperado.")
    if not 1 <= len(frame) <= MAX_REGIONS:
        raise DocumentError("Debes revisar al menos una región (máximo 50).")
    selected = {}
    for _, row in frame.iterrows():
        flag = row["incluir"]
        if isinstance(flag, str):
            flag = flag.strip().lower() in ("true", "1", "si", "sí", "yes")
        if not flag:
            continue
        page = int(row["pagina"])
        width, height = metadata["sizes"].get(str(page), [0, 0])
        coords = [int(row[k]) for k in ("x0", "y0", "x1", "y1")]
        x0, y0, x1, y1 = coords
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise DocumentError(f"Coordenadas inválidas en página {page}.")
        section = str(row["seccion"]).strip()
        if section not in SECTIONS:
            raise DocumentError(f"Sección desconocida: {section}.")
        if section in ("history", "other"):
            continue  # Never include unclassified or historical numbers.
        selected.setdefault(page, []).append({
            "section": section,
            "box": [x0 / width, y0 / height, x1 / width, y1 / height],
        })
    if not selected:
        raise DocumentError("Selecciona al menos una sección válida para extraer.")
    return selected


def preview_regions(filename, data, table, metadata):
    validated = validate_regions(table, metadata, data)
    output = []
    for page, image in _pages(filename, data):
        draw = ImageDraw.Draw(image)
        w, h = image.size
        for entry in validated.get(page, []):
            x0, y0, x1, y1 = entry["box"]
            box = (round(x0*w), round(y0*h), round(x1*w), round(y1*h))
            draw.rectangle(box, outline="#16a34a", width=4)
            draw.text((box[0], max(0, box[1]-14)), entry["section"], fill="#16a34a")
        output.append(image)
    return output


def preview_proposals(filename, data, rows):
    """Draw all raw AI proposals, including ones not yet classified."""
    output = []
    for page, image in _pages(filename, data):
        draw = ImageDraw.Draw(image)
        for index, row in enumerate(rows, start=1):
            if int(row[0]) != page:
                continue
            box = tuple(int(v) for v in row[2:6])
            draw.rectangle(box, outline="#2563eb", width=4)
            draw.text((box[0], max(0, box[1]-14)), f"Region {index}", fill="#2563eb")
        output.append(image)
    return output
