# Compatibilidad de plantillas InBody — etapa de extracción

Este módulo procesa reportes de composición corporal con OCR espacial (EasyOCR `detail=1`), conservando coordenadas normalizadas para evitar mezclar valores, ejes de gráficos y referencias.

## Plantillas reconocidas

- **InBody 580** (reporte con tabla segmental de masa magra, grasa, ECW y ángulo de fase): `inbody_mvp/layouts.py`.
- **Reporte español con siluetas** (secciones «Análisis de Magro por Segmentos», «Análisis de Grasa Segmental» e «Impedancia»): `inbody_mvp/layouts_es.py`.

El reporte español puede **no indicar un modelo de máquina inequívoco**: el extractor no inventa dicho identificador y requiere revisión manual.

## Variables de la plantilla española

- Composición corporal (agua corporal total, proteína, minerales, grasa, peso, masa muscular esquelética, BMI, PBF).
- Peso objetivo, ajustes, puntuación y variables de investigación cuando OCR identifica cifras en sus celdas.
- Masa magra segmental (kg) y su **porcentaje relativo a referencia**.
- Masa grasa segmental (kg) y su **porcentaje relativo a referencia**.
- Impedancia (`Ω`) en brazo derecho, brazo izquierdo, tronco, pierna derecha e izquierda, diferenciada por **20 y 100 kHz**.

**No** tratar masa magra segmental como masa muscular esquelética. **No** interpretar porcentajes relativos a referencia como porcentajes reales de composición en ese segmento. **No** crear evaluaciones adicionales a partir del historial impreso: todavía necesita un parser histórico independiente con fechas verificadas.

## Flujo y pruebas

1. Gradio en `app.py` recibe PDF/JPG/PNG; EasyOCR produce cajas con posiciones.
2. `extract_document()` detecta la plantilla; si coincide, usa el parser correspondiente.
3. Cada celda produce una medición **candidata**, con unidad, segmento, frecuencia y texto OCR original.
4. El usuario compara y corrige antes de exportar el borrador CSV. La app no almacena datos confirmados ni garantiza exactitud médica.

Ejecutar:

```bash
python -m pytest -q tests/test_layout_spanish.py tests/test_inbody_layouts.py tests/test_inbody_mvp.py tests/test_review.py
```

Las pruebas usan cajas OCR sintéticas y **no demuestran precisión con EasyOCR real**. El paso siguiente es un benchmark sobre reportes *anonimizados* de diferentes variantes, cuantificando recall por sección, cifras y metadatos.

**Privacidad:** No subir imágenes con cédula/nombre/QR o datos de salud reales a repositorios públicos ni Space QA público. Los fixtures deben ser sintéticos.
