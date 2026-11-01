"""Optional LOCAL document-layout AI + OCR per identified InBody section.

The vision model recognizes generic document regions (table/chart/title), NOT
the medical meaning of their contents. Section meaning is assigned from OCR
headings inside each region. All candidate values remain unconfirmed.

No remote image API calls; model weights are downloaded to the Space only when
explicitly enabled. No source images, text or identifiers are logged.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
import re
from typing import Any, Callable

import numpy as np
from PIL import Image

ALLOWED_LAYOUT_LABELS = {"table", "text", "header", "figure", "chart"}
OCR_SECTIONS = {
    "body_composition": re.compile(
        r"body composition analysis|an[aá]lisis de la composici[oó]n corporal", re.I
    ),
    "muscle_fat": re.compile(
        r"muscle.fat analysis|an[aá]lisis m[uú]sculo.grasa", re.I
    ),
    "obesity": re.compile(r"obesity analysis|an[aá]lisis de obesidad", re.I),
    "segmental_lean": re.compile(
        r"segmental lean analysis|an[aá]lisis de magro por segmentos", re.I
    ),
    "segmental_fat": re.compile(
        r"segmental fat analysis|an[aá]lisis de grasa segmental", re.I
    ),
    "research": re.compile(
        r"research parameters|par[aá]metros de investigaci[oó]n", re.I
    ),
    "impedance": re.compile(r"impedance|impedancia", re.I),
    "history": re.compile(
        r"body composition history|historial de composici[oó]n corporal", re.I
    ),
}
# Regions that may contain a single current examination's numeric results.
CURRENT_SECTIONS = set(OCR_SECTIONS) - {"history"}


@dataclass(frozen=True)
class LayoutRegion:
    label: str
    score: float
    # Absolute coordinates in the original image; not model-normalized.
    box: tuple[int, int, int, int]


@dataclass(frozen=True)
class SectionOCR:
    section: str
    model_label: str
    confidence: float
    box: tuple[int, int, int, int]
    detections: tuple[tuple[Any, str, float], ...]


def ai_sections_requested() -> bool:
    return os.getenv("ENABLE_AI_SECTION_OCR", "").strip().lower() in (
        "1", "true", "yes",
    )


@lru_cache(maxsize=1)
def _layout_model():
    """Keep heavy optional dependencies out of the normal ZeroGPU startup."""
    # Must be set before importing PaddleX / PaddleOCR.
    # Avoid the oneDNN CPU execution path that fails on PIR array attributes.
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
    try:
        from paddleocr import LayoutDetection
    except ImportError as exc:
        raise RuntimeError(
            "OCR por secciones requiere paddleocr y paddlepaddle; "
            "instala requirements-ai.txt en un entorno compatible."
        ) from exc
    return LayoutDetection(model_name="PP-DocLayout-S", device="cpu")


def _model_payload(result: Any) -> dict:
    """PaddleX result supports .json, where the data may be under res."""
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if not isinstance(payload, dict):
        if isinstance(result, dict):
            payload = result
        else:
            return {}
    return payload.get("res", payload)


def ai_detect_layout(image: Image.Image) -> list[LayoutRegion]:
    """Run a PRETRAINED vision model to locate document blocks on-device."""
    w, h = image.size
    predictions = _layout_model().predict(
        np.asarray(image.convert("RGB")), batch_size=1,
    )
    found = []
    for prediction in predictions:
        for box in _model_payload(prediction).get("boxes", []):
            label = str(box.get("label", "")).strip().lower()
            if label not in ALLOWED_LAYOUT_LABELS:
                continue
            score = float(box.get("score", 0))
            coords = box.get("coordinate")
            if not isinstance(coords, (list, tuple)) or len(coords) != 4:
                continue
            if score < .55:
                continue
            try:
                x0, y0, x1, y1 = (int(float(z)) for z in coords)
            except (TypeError, ValueError, OverflowError):
                continue
            x0, y0, x1, y1 = (
                max(0, min(w, x0)), max(0, min(h, y0)),
                max(0, min(w, x1)), max(0, min(h, y1)),
            )
            if x1 - x0 < 30 or y1 - y0 < 15:
                continue
            found.append(LayoutRegion(label, score, (x0, y0, x1, y1)))
    # Hard limit against model over-detection / repeated GPU OCR.
    return sorted(found, key=lambda z: -z.score)[:16]


def classify_section(text: str) -> str | None:
    """Use explicit text evidence; never infer a medical section from layout alone."""
    # History must win over general body-composition titles.
    if OCR_SECTIONS["history"].search(text):
        return "history"
    for name, pattern in OCR_SECTIONS.items():
        if name != "history" and pattern.search(text):
            return name
    return None


def _map_boxes(detections: list, left: int, top: int, scale: float) -> tuple:
    output = []
    for item in detections:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        points, text = item[:2]
        if not isinstance(points, (tuple, list)) or len(points) < 4:
            continue
        try:
            coords = [[left + float(x) / scale, top + float(y) / scale]
                      for x, y in points]
            score = float(item[2]) if len(item) >= 3 else .5
        except (TypeError, ValueError, IndexError):
            continue
        output.append((coords, str(text), score))
    return tuple(output)


def inspect_sections(
    image: Image.Image,
    ocr: Callable[[Image.Image], str | list],
    *,
    detect: Callable[[Image.Image], list[LayoutRegion]] = ai_detect_layout,
    max_sections: int = 10,
) -> list[SectionOCR]:
    """AI layout detection FIRST, then section-scoped OCR with provenance.

    Sections without a recognized heading are not trusted for measurements.
    History graphs are never input to the current-exam measurement parser.
    """
    all_results = []
    width, height = image.size
    for reg in detect(image):
        if len(all_results) >= max_sections:
            break
        if reg.label not in ALLOWED_LAYOUT_LABELS:
            continue
        x0, y0, x1, y1 = reg.box
        # Add enough padding to capture a title just above a table, but do not
        # broaden the crop into the history graph or neighbouring sections.
        pad_x = max(0, round((x1 - x0) * .02))
        pad_top = min(28, round(height * .015))
        left, top = max(0, x0-pad_x), max(0, y0-pad_top)
        right, bottom = min(width, x1+pad_x), min(height, y1)
        if right <= left or bottom <= top:
            continue
        crop = image.crop((left, top, right, bottom))
        scale = 2.0 if max(crop.size) < 1100 else 1.0
        if scale > 1:
            crop = crop.resize(
                (round(crop.width * scale), round(crop.height * scale)),
                Image.Resampling.LANCZOS,
            )
        tokens = ocr(crop)
        if not isinstance(tokens, list):
            continue  # Positional provenance is required for safe field matching.
        from .layouts import normalize_detections, tokens_to_text
        section_text = tokens_to_text(
            normalize_detections(tokens, crop.width, crop.height)
        )
        section = classify_section(section_text)
        if section is None:
            continue
        mapped = _map_boxes(tokens, left, top, scale)
        all_results.append(SectionOCR(
            section, reg.label, reg.score, (left, top, right, bottom), mapped,
        ))
    return all_results


def merge_section_ocr(
    full_page_detections: list,
    regions: list[SectionOCR],
    *,
    max_new: int = 300,
) -> tuple[list, list[str]]:
    """Prefer clearer OCR tokens in identified CURRENT sections only.

    A section with unknown meaning or a history plot can NEVER contribute
    new measurement values. Duplicates use box center/size, not raw labels.
    """
    merged = list(full_page_detections)
    notices = []
    added = 0
    for region in regions:
        if region.section == "history":
            notices.append("Se excluyó el historial gráfico de las medidas actuales.")
            continue
        if region.section not in CURRENT_SECTIONS:
            continue
        accepted = 0
        for candidate in region.detections:
            if added >= max_new:
                break
            points, value, score = candidate
            if score < .60:
                continue
            try:
                xc = sum(float(p[0]) for p in points) / len(points)
                yc = sum(float(p[1]) for p in points) / len(points)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            # Avoid duplicating any token that is already localized accurately.
            matches = []
            for idx, t in enumerate(merged):
                try:
                    xs = [float(p[0]) for p in t[0]]
                    ys = [float(p[1]) for p in t[0]]
                except (TypeError, ValueError, IndexError):
                    continue
                txc, tyc = sum(xs)/len(xs), sum(ys)/len(ys)
                if abs(xc - txc) < 14 and abs(yc - tyc) < 12:
                    matches.append(idx)
            if matches:
                existing = merged[matches[0]]
                old_score = float(existing[2]) if len(existing)>2 else 0
                # Only replace if section OCR is meaningfully more confident.
                if score > old_score + .10:
                    merged[matches[0]] = candidate
                    accepted += 1
            else:
                merged.append(candidate)
                added += 1
                accepted += 1
        notices.append(
            f"Sección {region.section}: OCR especializado "
            f"({accepted} bloques nuevos o mejorados; pendiente de revisión)."
        )
    return merged, notices
