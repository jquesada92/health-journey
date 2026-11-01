# Gemini Flash: revisión y auditoría por medición

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
- GEMINI_API_KEY como secreto; GEMINI_MODEL opcional (gemini-2.5-flash por defecto).
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
