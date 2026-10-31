# Health Journey — InBody Hub, Fase 1 (Flask + Dash)

Esta implementación **coexiste** con `app.py` (Gradio en Hugging Face Space), que no se modifica.

## Objetivo

Probar una pantalla para cargar **PDF, JPG, JPEG y PNG**, extraer texto con PyMuPDF o EasyOCR según el contenido, detectar mediciones conocidas y desconocidas, revisar resultados editables y descargar un **CSV borrador en formato vertical**.

Los documentos **no se guardan en PostgreSQL ni en archivos**. La información extraída se mantiene temporalmente en el navegador durante la sesión. No hay autenticación todavía: usar en local con muestras anonimizadas. No publicar esta versión como servicio abierto.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python dash_app.py
```

Abrir http://127.0.0.1:8050. La primera ejecución de EasyOCR puede descargar modelos y funcionar en CPU; para PDFs con texto embebido **no se requiere OCR**.

Pruebas: `python -m pytest -q tests/test_inbody_mvp.py` (`pip install pytest` si aún no está disponible).

## Tratamiento de archivos

- **PDF**: extraer texto directamente por página. Si una página no contiene suficiente texto, renderizarla con PyMuPDF y realizar OCR con EasyOCR.
- **JPG/JPEG/PNG**: validar contenido real, corregir orientación EXIF y ejecutar EasyOCR.
- Máximo **15 MB**, **8 páginas** y **20 millones de píxeles** en una imagen. Rechaza otros tipos, corruptos y PDFs cifrados.
- La extracción y clasificación son **heurísticas conservadoras**: en esta fase una tabla compleja puede necesitar corrección. Cada resultado está marcado para revisión y preserva etiqueta original y texto fuente.
- Reconoce `phase_angle`, incluida región y frecuencia *solo si aparecen explícitamente*. Distingue `segmental_lean_mass` de `skeletal_muscle_mass`.
- Conserva las métricas desconocidas como `sin_clasificar`, sin descartar el número de origen. Las unidades ausentes permanecen vacías.
- La edad se calcula desde nacimiento y fecha del examen, o se conserva como *reportada* si solo existe esa edad.
- Si falta la hora, el `timestamp` no se inventa. Si aparece hora pero no zona horaria, se etiqueta para revisión.

## Interfaz de revisión

La tabla permite editar el nombre normalizado, segmento, frecuencia, unidad y valor. También se pueden modificar metadatos del examen. El botón exporta un **borrador**, no lo persiste ni lo confirma. Columnas CSV:

`id_persona,modelo_inbody,timestamp,variable_medida,unidad_medida,valor_medida,edad`

Para no colisionar mediciones segmentales en estas siete columnas, el identificador exportado agrega sufijos `__left_leg`, `__right_leg`, `__50khz`, etc. La versión futura almacenará estos atributos separados en un modelo relacional.

## Límites conocidos y próximos pasos

1. Validar precisión con informes InBody anonimizados de distintos modelos; mejorar lectura de tablas y OCR.
2. Separar extracción de etiquetas, medidas y dimensiones en catálogos configurables versionados, antes de persistir.
3. Incorporar identidad interna de persona, confirmación humana, detección de duplicados y PostgreSQL/Alembic.
4. Añadir paneles Plotly de tendencias totales y segmentales, sin equiparar medidas no comparables.
5. Migrar el entorno QA a un **Docker Space** para Flask + Dash si se decide desplegar ahí; el `README.md` existente declara `sdk: gradio` y por ello no puede lanzar esta app Dash sin cambiar el tipo de Space.

**Importante:** no se usa Hugging Face AI/VLM todavía. Primero se medirá la calidad de extracción determinista + OCR. No introducir comparaciones clínicas automatizadas.
