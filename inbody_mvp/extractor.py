"""Conservative InBody PDF/JPEG/PNG extraction for a human-reviewed MVP.

No file contents or measurements are stored by this module. AI-based enrichment,
SQL persistence and longitudinal comparability are intentionally out of scope.
"""
from __future__ import annotations

import hashlib
import io
import re
import threading
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Any

import fitz
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from .language import ReportLanguage, detect_report_language

from .layouts import extract_inbody580, normalize_detections, tokens_to_text
from .layouts_es import extract_spanish_silhouette

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PAGES = 8
MAX_PIXELS = 20_000_000
OCR_DPI = 155

OcrFunction = Callable[[Image.Image], str | list[Any]]
_OCR_READER = None
_OCR_LOCK = threading.Lock()


class DocumentError(ValueError):
    """The uploaded file is not usable or exceeds phase-1 limits."""


class Measurement(BaseModel):
    original_label: str
    variable_medida: str
    categoria: str = "sin_clasificar"
    dimension: str = "desconocida"
    unidad_medida: str | None = None
    valor_medida: float
    segmento: str | None = None
    frecuencia_khz: float | None = None
    pagina: int = Field(ge=1)
    fuente: str
    texto_fuente: str
    revisar: bool = True


class ExtractionResult(BaseModel):
    archivo: str
    hash_sha256: str
    tipo_archivo: str
    idioma_reporte: ReportLanguage = "UNKNOWN"
    id_persona: str | None = None
    modelo_inbody: str | None = None
    timestamp: str | None = None
    edad: int | None = None
    origen_edad: str | None = None
    medidas: list[Measurement] = Field(default_factory=list)
    texto_por_pagina: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)


# The source must say which unit is being measured. The classifier does not invent it.
KNOWN_METRICS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("phase_angle", (r"\bphase\s*angle\b", r"\bangulo\s+de\s+fase\b", r"\bpha\b"), "bioimpedancia", "angulo"),
    ("body_fat_percentage", (r"\bpercent(?:age)?\s+body\s+fat\b", r"\bpbf\b", r"\bporcentaje\s+(?:de\s+)?grasa\b", r"\bgrasa\s+corporal\s*\(%\)"), "grasa", "porcentaje"),
    ("body_fat_mass", (r"\bbody\s+fat\s+mass\b", r"\bmasa\s+(?:de\s+)?grasa\b", r"\bgrasa\s+corporal\b"), "grasa", "masa"),
    ("skeletal_muscle_mass", (r"\bskeletal\s+muscle\s+mass\b", r"\bsmm\b", r"\bmasa\s+muscular\s+esqueletica\b"), "musculo", "masa"),
    ("segmental_lean_mass", (r"\bsegmental\s+lean\s+mass\b", r"\bmasa\s+magra\s+segmental\b", r"\bmasa\s+libre\s+de\s+grasa\b"), "masa_libre_grasa", "masa"),
    ("total_body_water", (r"\btotal\s+body\s+water\b", r"\btbw\b", r"\bagua\s+corporal\s+total\b"), "agua", "volumen"),
    ("ecw_tbw_ratio", (r"\becw\s*/\s*tbw\b", r"\brelacion\s+agua\s+extracelular\b"), "hidratacion", "razon"),
    ("visceral_fat_area", (r"\bvisceral\s+fat\s+area\b", r"\barea\s+de\s+grasa\s+visceral\b"), "grasa", "area"),
    ("weight", (r"\bweight\b", r"\bpeso\b"), "peso", "masa"),
    ("impedance", (r"\bimpedance\b", r"\bimpedancia\b"), "bioimpedancia", "resistencia"),
    ("reactance", (r"\breactance\b", r"\breactancia\b"), "bioimpedancia", "resistencia"),
)

# Header fields must never be mistaken for a body-composition measurement.
HEADER_LABEL_RE = re.compile(
    r"^(?:id|person\s*id|patient\s*id|cedula|identificacion|documento|nombre|name|edad|age|sexo|sex|gender|fecha|date|time|hora|model|modelo|inbody(?:\s*model)?|height|estatura|nacimiento|birth)\b",
    re.I,
)

UNIT_RE = re.compile(r"(?:kcal\s*/\s*day|kcal\s*/\s*d(?:ia)?|cm\s*(?:\^?2|²)|kg|lbs?|lb|%|°|degrees?|grados?|ohms?|Ω|liters?|litros?|ml|l)", re.I)
MEASURE_RE = re.compile(
    r"^\s*(?P<label>[^\n]{3,120}?)\s*[:\t ]+\s*"
    r"(?P<value>-?\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>kcal\s*/\s*day|kcal\s*/\s*d(?:ia)?|cm\s*(?:\^?2|²)|kg|lbs?|lb|%|°|degrees?|grados?|ohms?|Ω|liters?|litros?|ml|l)?\s*$",
    re.I,
)
DOB_RE = re.compile(r"(?:fecha\s+(?:de\s+)?nacimiento|birth\s*date|dob)\s*[:#]?\s*(\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4})", re.I)
DATE_RE = re.compile(
    # Printed InBody headers often put the label and value on different
    # lines, and terminate the year with a dot: "04.10.2026. 10:04".
    # Restrict to at most ONE newline after an explicit exam-date label
    # so a DOB or a date in the history chart is not mistaken for the exam.
    r"^[ \t]*(?:test[ \t]+date(?:[ \t]*(?:/|&|and)[ \t]*time)?|"
    r"fecha[ \t]*(?:/|y|&)[ \t]*hora"
    r"(?:[ \t]+(?:del|de)[ \t]+(?:test|examen|prueba))?|"
    r"fecha(?:[ \t]+de[ \t]+(?:la[ \t]+)?"
    r"(?:prueba|examen|medici[oó]n))?|"
    r"measurement[ \t]+date|date[ \t]*(?:/|&|and)[ \t]*time|"
    r"date(?:[ \t]+of[ \t]+(?:the[ \t]+)?"
    r"(?:test|measurement))?)"
    r"[ \t]*[:#-]?[ \t]*(?:\n[ \t]*)?"
    r"(\d{4}[/.-]\d{1,2}[/.-]\d{1,2}|"
    r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4})"
    r"\.?(?:[ \t]+(\d{1,2}:\d{2}(?::\d{2})?))?",
    re.I | re.M,
)
TIME_RE = re.compile(
    r"^[ \t]*(?:hora(?:\s+(?:de\s+)?(?:prueba|examen|medici[oó]n))?|time)"
    r"\s*[:#-]?\s*(\d{1,2}:\d{2}(?::\d{2})?)\b",
    re.I | re.M,
)
ID_RE = re.compile(r"(?:c[eé]dula|identificaci[oó]n|documento|patient\s*id|person\s*id|\bID\b)\s*[:#]\s*([\w.-]{4,35})", re.I)
MODEL_RE = re.compile(r"\bInBody\s*[-:]?\s*(\d{2,4})\b", re.I)
AGE_RE = re.compile(r"(?:\bedad\b|\bage\b)\s*[:#]?\s*(\d{1,3})\b", re.I)
FREQ_RE = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*k\s*hz\b", re.I)


def normalized(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def detect_segment(label: str) -> str | None:
    s = normalized(label)
    segments = (
        ("left_leg", ("pierna izquierda", "left leg", "left lower limb")),
        ("right_leg", ("pierna derecha", "right leg", "right lower limb")),
        ("left_arm", ("brazo izquierdo", "left arm", "left upper limb")),
        ("right_arm", ("brazo derecho", "right arm", "right upper limb")),
        ("trunk", ("tronco", "trunk")),
        ("whole_body", ("whole body", "cuerpo completo", "corporal total")),
    )
    for value, names in segments:
        if any(name in s for name in names):
            return value
    return None


def classify_measure(label: str, unit: str | None) -> tuple[str, str, str, str | None, float | None, bool]:
    s = normalized(label)
    key, category, dimension = "sin_clasificar", "sin_clasificar", "desconocida"
    for metric, patterns, cat, dim in KNOWN_METRICS:
        if any(re.search(regex, s) for regex in patterns):
            key, category, dimension = metric, cat, dim
            break
    unit = (unit or "").strip()
    if not unit:
        paren = re.search(r"\((kg|%|°|Ω|ohm|l|cm²|cm2)\)", label, re.I)
        unit = paren.group(1) if paren else ""
    if unit.lower() in ("degrees", "degree", "grados", "grado"):
        unit = "°"
    if unit.lower() in ("ohm", "ohms"):
        unit = "Ω"
    if unit.lower() in ("cm2", "cm^2"):
        unit = "cm²"
    if unit.lower() in ("liters", "litros", "l"):
        unit = "L"
    if unit.lower() == "ml":
        unit = "mL"
    freq = FREQ_RE.search(label)
    freq_khz = float(freq.group(1).replace(",", ".")) if freq else None
    # A classifier match is not a guarantee of comparable or correct data.
    return key, category, dimension, unit or None, freq_khz, key == "sin_clasificar"


def _parse_date(value: str) -> date | None:
    # Do not guess ambiguous dates with 2-digit years or impossible values.
    sep = re.split(r"[/.-]", value)
    if len(sep) != 3 or len(sep[0]) == 2 and len(sep[2]) != 4:
        return None
    try:
        if len(sep[0]) == 4:
            return date(int(sep[0]), int(sep[1]), int(sep[2]))
        if len(sep[2]) == 4:
            # Latin-American DD/MM/YYYY is conventional; ambiguous input flagged separately.
            return date(int(sep[2]), int(sep[1]), int(sep[0]))
    except ValueError:
        return None
    return None


def parse_text(
    page_texts: list[tuple[str, str]], filename: str = "report.pdf", digest: str = ""
) -> ExtractionResult:
    """Parse (text, extraction_method) pairs; all candidates require manual review."""
    text_all = "\n".join(page for page, _ in page_texts)
    language = detect_report_language(text_all)
    ident = ID_RE.search(text_all)
    model = MODEL_RE.search(text_all)
    dtmatch = DATE_RE.search(text_all)
    date_exam = _parse_date(dtmatch.group(1)) if dtmatch else None
    tmatch = dtmatch.group(2) if dtmatch and dtmatch.group(2) else None
    if not tmatch:
        m = TIME_RE.search(text_all)
        tmatch = m.group(1) if m else None
    timestamp = None
    if date_exam and tmatch:
        try:
            clock = datetime.strptime(tmatch, "%H:%M:%S" if tmatch.count(":") == 2 else "%H:%M").time()
            timestamp = datetime.combine(date_exam, clock).isoformat(timespec="seconds")
        except ValueError:
            pass
    warnings: list[str] = []
    if date_exam is None:
        warnings.append("Fecha del examen no identificada; no se inventa un timestamp.")
    elif timestamp is None:
        warnings.append("No hay hora verificable: fecha encontrada, timestamp pendiente de revisión.")
    if timestamp:
        warnings.append("Timestamp sin zona horaria: confirmar la zona local del examen antes de almacenar.")
    age, age_source = None, None
    dobmatch = DOB_RE.search(text_all)
    birth = _parse_date(dobmatch.group(1)) if dobmatch else None
    if birth and date_exam and birth <= date_exam:
        age = date_exam.year - birth.year - ((date_exam.month, date_exam.day) < (birth.month, birth.day))
        if 0 <= age <= 120:
            age_source = "calculada_desde_fecha_nacimiento"
        else:
            age = None
    if age is None:
        m = AGE_RE.search(text_all)
        if m and 0 <= int(m.group(1)) <= 120:
            age, age_source = int(m.group(1)), "reportada_no_calculada"
    if age is None:
        warnings.append("Edad desconocida: falta fecha de nacimiento o edad reportada.")

    measures: list[Measurement] = []
    seen: set[tuple] = set()
    for page_number, (text, engine) in enumerate(page_texts, 1):
        for line in text.splitlines():
            clean = " ".join(line.strip().split())
            if not clean or HEADER_LABEL_RE.match(normalized(clean)):
                continue
            match = MEASURE_RE.fullmatch(clean)
            if not match:
                continue
            label = match.group("label").strip(" :-\t")
            if not re.search(r"[A-Za-zÀ-ÿ]", label):
                continue
            try:
                value = float(match.group("value").replace(",", "."))
            except ValueError:
                continue
            metric, cat, dim, unit, freq, unclassified = classify_measure(label, match.group("unit"))
            segment = detect_segment(label)
            dedup = (page_number, normalized(label), value, unit, segment, freq)
            if dedup in seen:
                continue
            seen.add(dedup)
            measures.append(Measurement(
                original_label=label, variable_medida=metric,
                categoria=cat, dimension=dim, unidad_medida=unit,
                valor_medida=value, segmento=segment, frecuencia_khz=freq,
                pagina=page_number, fuente=engine, texto_fuente=clean,
                revisar=True,
            ))
            if unclassified:
                warnings.append(f"Variable no reconocida en página {page_number}: {label!r}.")
    if not ident:
        warnings.append("Cédula / ID no encontrado: introducirlo manualmente.")
    if not model:
        warnings.append("Modelo InBody no identificado: introducirlo manualmente.")
    if not measures:
        warnings.append("No se detectaron mediciones en líneas completas; inspeccionar el texto y corregir manualmente.")
    return ExtractionResult(
        archivo=filename, hash_sha256=digest,
        idioma_reporte=language,
        tipo_archivo=Path(filename).suffix.lower().lstrip("."),
        id_persona=ident.group(1) if ident else None,
        modelo_inbody=f"InBody {model.group(1)}" if model else None,
        timestamp=timestamp, edad=age, origen_edad=age_source,
        medidas=measures, texto_por_pagina=[p for p, _ in page_texts],
        advertencias=list(dict.fromkeys(warnings)),
    )


def validate_file(filename: str, data: bytes) -> str:
    """Validate both extension and signature; a renamed file is not accepted."""
    if not data:
        raise DocumentError("El archivo está vacío.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError("El archivo supera el límite de 15 MB.")
    suffix = Path(filename or "").suffix.lower()
    kind = {".pdf": "pdf", ".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png"}.get(suffix)
    if not kind:
        raise DocumentError("Solo se permiten PDF, JPG, JPEG o PNG.")
    sniffed = (
        "pdf" if data.startswith(b"%PDF-") else
        "png" if data.startswith(b"\x89PNG\r\n\x1a\n") else
        "jpeg" if data.startswith(b"\xff\xd8\xff") else None
    )
    if sniffed != kind:
        raise DocumentError("La extensión no coincide con el contenido del archivo.")
    return kind


def _default_ocr(image: Image.Image) -> str:
    global _OCR_READER
    try:
        import easyocr  # Lazy loading: native PDF text works without downloading OCR weights.
        import numpy as np
    except ImportError as ex:
        raise DocumentError("EasyOCR o NumPy no están instalados; el OCR no está disponible.") from ex
    with _OCR_LOCK:
        if _OCR_READER is None:
            _OCR_READER = easyocr.Reader(["es", "en"], gpu=False)
        detections = _OCR_READER.readtext(np.asarray(image.convert("RGB")), detail=1, paragraph=False)
    return detections


def _load_image(data: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as src:
            if src.width * src.height > MAX_PIXELS:
                raise DocumentError("La imagen supera los 20 megapíxeles permitidos.")
            src.verify()
        with Image.open(io.BytesIO(data)) as src:
            return ImageOps.exif_transpose(src).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as ex:
        raise DocumentError("La imagen está corrupta o no se puede abrir.") from ex


def extract_document(filename: str, data: bytes, ocr: OcrFunction | None = None) -> ExtractionResult:
    """Extract text from PDFs/JPEGs/PNGs and parse candidates without persistence."""
    kind = validate_file(filename, data)
    digest = hashlib.sha256(data).hexdigest()
    ocr_engine = ocr or _default_ocr
    texts: list[tuple[str, str]] = []
    notices: list[str] = []
    positional_pages: list[tuple[int, list, int, int]] = []

    def read_ocr(image: Image.Image, page_number: int) -> str:
        try:
            answer = ocr_engine(image)
        except DocumentError:
            raise
        except Exception as exc:
            # The original error may include document-derived text or private
            # filesystem paths. Surface only its class, never its arguments.
            raise DocumentError(
                f"Falló el motor OCR en la página {page_number} "
                f"({type(exc).__name__}); verifica el runtime y sus logs privados."
            ) from exc
        if isinstance(answer, str):
            text_value = answer.strip()
        elif isinstance(answer, list):
            tokens = normalize_detections(answer, image.width, image.height)
            positional_pages.append((page_number, answer, image.width, image.height))
            text_value = tokens_to_text(tokens).strip()
        else:
            raise DocumentError(
                f"El motor OCR devolvió un tipo no soportado en la página {page_number}."
            )
        if not text_value:
            raise DocumentError(
                f"El OCR no reconoció texto en la página {page_number}. "
                "Revisa la calidad, orientación y resolución del documento."
            )
        return text_value
    if kind == "pdf":
        try:
            with fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass:
                    raise DocumentError("No se permiten PDFs protegidos por contraseña.")
                if len(pdf) > MAX_PAGES:
                    raise DocumentError(f"Máximo {MAX_PAGES} páginas por archivo.")
                for n, page in enumerate(pdf):
                    native = page.get_text("text", sort=True).strip()
                    if len(native) >= 70:
                        texts.append((native, "pdf_text"))
                        continue
                    if page.rect.width * page.rect.height * (OCR_DPI / 72)**2 > MAX_PIXELS:
                        raise DocumentError("Una página excede el tamaño máximo para OCR.")
                    pixmap = page.get_pixmap(dpi=OCR_DPI, colorspace=fitz.csRGB, alpha=False)
                    picture = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                    try:
                        scanned = read_ocr(picture, n + 1)
                    except DocumentError as exc:
                        # A scanned page has no text fallback. Never silently
                        # claim a successful extraction when OCR failed.
                        if not native:
                            raise
                        scanned = ""
                        notices.append(
                            f"Página {n+1}: no se pudo completar el OCR; "
                            "solo se conserva texto nativo parcial."
                        )
                    texts.append(("\n".join(filter(None, [native, scanned])), "ocr" if scanned else "pdf_text"))
        except DocumentError:
            raise
        except (fitz.FileDataError, RuntimeError, ValueError) as ex:
            raise DocumentError("El PDF está corrupto o no se puede leer.") from ex
    else:
        picture = _load_image(data)
        # An image has no native-text fallback. Raise an actionable error
        # instead of returning zero candidates after OCR has failed.
        text = read_ocr(picture, 1)
        texts.append((text, "ocr"))
    result = parse_text(texts, filename=filename, digest=digest)
    for page_number, detections, width, height in positional_pages:
        rows, metadata = extract_inbody580(detections, width, height)
        if not metadata:
            rows, metadata = extract_spanish_silhouette(detections, width, height)
        if not metadata:
            continue
        if metadata.get("layout") == "spanish_silhouette":
            # Positional header matching owns identity and exam date; do not
            # inherit invented identifiers/model numbers from joined OCR text.
            result.id_persona = None
            result.modelo_inbody = None
            result.timestamp = None
            result.edad, result.origen_edad = None, None
            result.medidas = []
        if rows:
            # Positional, multi-column layout: don't interpret chart-axis values
            # as a simple "label value unit" text line.
            result.advertencias = [w for w in result.advertencias
                                  if not w.startswith("Variable no reconocida")]
            result.medidas = [Measurement.model_validate({**row, "pagina": page_number})
                             for row in rows]
            if metadata.get("layout") == "spanish_silhouette":
                notices.extend(metadata.get("warnings", []))
            else:
                notices.extend([
                    "Plantilla InBody 580: revisar todas las mediciones candidatas "
                    "contra el reporte original antes de exportar.",
                    "El historial gráfico impreso no se incorpora como nuevos "
                    "exámenes; requiere un extractor histórico específico.",
                ])
        result.modelo_inbody = metadata.get("modelo_inbody") or result.modelo_inbody
        result.id_persona = metadata.get("id_persona") or result.id_persona
        exam = _parse_date(metadata["exam_date_raw"]) if metadata.get("exam_date_raw") else None
        birth = _parse_date(metadata["dob_raw"]) if metadata.get("dob_raw") else None
        clock = metadata.get("exam_time_raw")
        if exam and clock:
            try:
                result.timestamp = datetime.combine(
                    exam, datetime.strptime(clock, "%H:%M").time()
                ).isoformat(timespec="seconds")
                notices.append("Timestamp del reporte sin zona horaria verificada.")
            except ValueError:
                pass
        if exam and birth and birth <= exam:
            calc = exam.year - birth.year - ((exam.month, exam.day) < (birth.month, birth.day))
            if 0 <= calc <= 120:
                result.edad, result.origen_edad = calc, "calculada_desde_fecha_nacimiento"
        elif metadata.get("age_raw") is not None and 0 <= metadata["age_raw"] <= 120:
            result.edad, result.origen_edad = metadata["age_raw"], "reportada_no_calculada"
    if result.medidas:
        result.advertencias = [w for w in result.advertencias
                              if not w.startswith("No se detectaron mediciones")]
    if result.timestamp:
        result.advertencias = [w for w in result.advertencias if not w.startswith(
            ("Fecha del examen no identificada", "No hay hora verificable"))]
    if result.edad is not None:
        result.advertencias = [w for w in result.advertencias
                              if not w.startswith("Edad desconocida")]
    result.advertencias = list(dict.fromkeys(notices + result.advertencias))
    return result
