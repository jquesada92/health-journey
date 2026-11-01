# Gemini Flash: revisión y auditoría por medición

## Extracción en inglés y vista local del documento (flujo actual)

El modelo Gemini interpreta informes InBody en español o inglés y devuelve
`section`, `measurement` y `missing_or_unreadable` **siempre en inglés**.
Se utilizan nombres consistentes: `Body Composition Analysis`,
`Muscle-Fat Analysis`, `Obesity Analysis`, `Segmental Lean Analysis`,
`Segmental Fat Analysis`, `InBody Score` e `Impedance`.
En mediciones segmentales, el nombre sigue
`Right Arm - Lean Mass`, `Left Leg - Fat Mass` o
`Right Arm - Frequency` (frecuencia por fila, en `kHz`).
El valor de impedancia se registra aparte:
`Right Arm - Impedance at 50 kHz`, en `Ω`.
La unidad de puntaje es `points`, no `puntos`.

Los identificadores, marcas de tiempo, nombres de archivo y números
**no** se traducen ni alteran. `value` sigue siendo cadena textual,
preservando exactamente `8.20`, `0.370` y ceros a la izquierda del ID.
Se excluyen completamente las gráficas y valores históricos. El usuario
puede corregir `section`, `measurement`, `value` y `unit`, pero
debe mantener los nombres de mediciones corregidos en inglés.
El comentario libre de auditoría se conserva en el idioma escrito por
la persona para no modificar evidencia original. El JSON original de
Gemini permanece disponible para auditoría.

La pestaña **InBody Upload** ahora coloca una **vista de PDF/imagen
junto a la tabla editable**. PyMuPDF y Pillow rasterizan localmente
cada página (máximo 10 y 15 MB por archivo, aplicando los controles del
extractor). Gradio `Gallery` muestra miniaturas y ofrece ampliación
al pulsar una página. No requiere `gradio_pdf`, OCR ni GPU; la
vista aparece después de cargar, antes de cualquier envío remoto a Gemini.
Se desactivan los botones de compartir y descargar la previsualización.
Al cambiar o limpiar el archivo se resetean resultados, comentarios
y consentimiento de envío/almacenamiento anteriores.

La previsualización utiliza el caché de medios de Gradio para el navegador
y **no supone aislamiento de archivos personales en un Space público**.
Utilizar únicamente reportes sintéticos/anonimizados en QA; un despliegue
para datos identificables requiere control de acceso privado efectivo.
El visor no interpreta ni extrae contenido histórico; solo muestra
el documento original para comparación humana.

Tests sintéticos: `tests/test_inbody_document_preview.py`
(verificación de multipágina PDF, PNG, límite de páginas,
limpieza de estados, prompt inglés). No se envían archivos a Gemini
ni se modifica Neon por el hecho de mostrar un PDF.



## Modelos Gemini y error 404 (noviembre de 2026)

La configuración anterior utilizaba `gemini-2.5-flash`. Google restringe
el acceso a esa familia para proyectos que no la utilizaban previamente.
El valor predeterminado nuevo es `gemini-3.8-flash`, compatible con
imágenes y salidas estructuradas y sujeto al nivel de uso de la clave.
Si existe `GEMINI_MODEL` como variable de Hugging Face, prevalece su valor
sobre el predeterminado; revisar Settings → Variables and secrets.

En la interfaz, el acordeón **Diagnóstico de la API de Gemini** ofrece
**Comprobar modelos disponibles**: consulta `client.models.list()` y filtra
los modelos Flash con `supported_actions` que incluyen `generateContent`.
Esta consulta **no envía el documento InBody**. Si Gemini responde HTTP 404,
la aplicación muestra el modelo solicitado y, si puede recuperarlos,
los modelos Flash accesibles a esa API key, sin exponer secretos ni datos
personales. No realiza cambios de modelo ni reintentos facturables de
forma automática.

La existencia de un modelo en la lista no garantiza cuota ni precio
gratuito para una cuenta concreta. Revisar condiciones de retención de
datos del nivel gratuito antes de usar informes identificables.


## Contrato API Gemini para JSON estructurado (corrección 400 INVALID_ARGUMENT)

En `inbody_mvp/gemini_review.py`, `Extraction`, `Header` y `Measurement`
utilizan `ConfigDict(extra="forbid")` para rechazar campos desconocidos.
Esto genera `additionalProperties: false` en el JSON Schema de Pydantic.
Con `response_schema=Extraction`, algunas versiones de `google-genai`
transforman ese campo a `additional_properties` al serializar la
configuración OpenAPI y Gemini responde **400 INVALID_ARGUMENT**.

**Contrato obligatorio:** usar `response_json_schema=Extraction.model_json_schema()`
junto con `response_mime_type="application/json"`; no establecer
`response_schema` a la vez. Continuar validando la respuesta en Python con
`Extraction.model_validate_json(response.text)` para preservar la política
de campos estrictos y valores decimales como texto (`"8.20"`).

Los fallos de API deben mostrar solo la categoría y código HTTP (400/401/
403/404/429/5xx), sin propagar mensajes brutos que podrían contener datos
privados, clave API o extractos de documentos. Las pruebas sintéticas
`tests/test_gemini_api_contract.py` simulan el SDK, verifican el contrato
HTTP y no utilizan Internet ni reportes identificables.


La pestaña InBody Upload sustituye el visor de secciones por extracción Gemini y tabla editable; se preservan los dashboards.

## Configuración
- Instalar requirements.txt.
- GEMINI_API_KEY como secreto; GEMINI_MODEL opcional (gemini-3.8-flash por defecto).
- En Neon privado aplicar migrations/004_gemini_measurement_audit.sql.
- Configurar DATABASE_URL con SSL, ENABLE_PERSISTENCE=1 y HF_ALLOWED_USERS para Spaces.
- Evitar cargar documentos identificables en Spaces públicos: Google recibe la imagen.

## Procedimiento
1. Cargar PDF/JPG/PNG y extraer con Gemini Flash.
2. Revisar cada fila, incluso si no necesita corrección.
3. Corregir value, unit, section o measurement; original_value permanece inmutable.
4. Completar correction_comment si hubo modificación y marcar reviewed en cada fila.
5. Validar revisión, aceptar el guardado privado y guardar.

was_corrected se calcula comparando contra la respuesta original; la columna mostrada no se toma como autoridad. El valor decimal permanece como texto, con validación Decimal, para conservar 8.20.

## Auditoría Neon
- hj_extraction_audits conserva archivo, encabezado, modelo y respuesta original completa de Gemini.
- hj_measurement_audits conserva la medición original y final, bandera de corrección, comentario y fecha de revisión.
- La operación es atómica y rechaza el mismo archivo dos veces.
- No se inserta en las tablas existentes hj_exams/hj_measurements: esta etapa de auditoría está separada del historial y dashboards.

## Pruebas
pytest tests/test_gemini_measurement_audit.py

Sin API key de Gemini y base Neon no se validan llamadas reales ni persistencia; estas pruebas verifican la lógica local de revisión.
