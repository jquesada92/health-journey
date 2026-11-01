# Gemini Flash: revisión y auditoría por medición


## Flujo actual: extracción inglés + PDF y consentimiento (noviembre 2026)

**UI:** InBody Upload coloca, antes del archivo, dos consentimientos
independientes (Gemini y Neon, ambos apagados). El PDF se renderiza
localmente en una galería Gradio 6 junto a la tabla editable; se
pueden inspeccionar páginas en pantalla completa. El visor no envía
el documento a Gemini. Al cargar otro archivo se revocan ambos
consentimientos y se limpian resultados anteriores.

**Extracción:** Gemini traduce los nombres al inglés, incluso si el
documento está en español: `Body Composition Analysis`,
`Segmental Lean Analysis`, `Right Arm - Lean Mass`,
`Right Arm - Frequency`, `InBody Score`. El número sigue como
texto exacto (ej. `8.20`) y cada frecuencia ocupa su propia fila.
No se extraen valores del historial. Se conserva la respuesta
original, la corrección y su comentario.

**Escritura sin OAuth:** la auditoría solo se guarda tras revisión
y consentimiento Neon. Se ejecuta `hj_submit_reviewed_audit(jsonb)`
usando una conexión **distinta** de `DATABASE_URL`:
`DEMO_DATABASE_URL` (Secret HF), usuario exacto
`health_journey_demo_writer`, SSL y
`ENABLE_ANONYMOUS_AUDIT=1` (Variable HF). El nuevo rol se crea en
`migrations/005_consent_only_audit_writer.sql` como `NOLOGIN`
para que un administrador establezca su contraseña por canal seguro
y habilite el login **después** de aplicar la migración. No usar
la creación automática de roles Neon: puede heredar
`neon_superuser`.

El rol solo puede ejecutar la función de inserción y no posee
permisos SELECT/INSERT/UPDATE/DELETE directos sobre las tablas.
La función valida límites de tamaño, metadatos, valores,
correcciones y registra todas las filas en una sola transacción.
El historial privado sigue requiriendo OAuth y no se expone al
público. Esto no constituye autenticación del remitente: se
necesitan protección antiabuso y hosting privado para datos
identificables. El dashboard público continúa independiente.

El cambio está preparado en rama y probado en una rama temporal
de Neon con datos sintéticos; **no desplegado en Neon main**.
No se modificaron tablas históricas ni usuarios existentes.


## Recuperación controlada ante HTTP 503

El SDK de Google ya utiliza reintentos exponenciales para errores
temporales. Si el modelo principal (`GEMINI_MODEL`, normalmente
`gemini-3.8-flash`) termina con **HTTP 503**, se intenta una sola vez
`GEMINI_FALLBACK_MODEL` (por defecto `gemini-3.5-flash-lite`).
No se reintenta la alternativa desde nuestra aplicación y no se
aplica el fallback ante HTTP 429, 400, 401, 403 o 404.

Usar `GEMINI_FALLBACK_MODEL=off` para desactivar el fallback. La
extracción con un segundo modelo puede variar de precisión y consumir
más solicitudes; todos los resultados requieren revisión humana.
La auditoría almacena el modelo que realmente produjo la extracción,
el modelo principal y un indicador de fallback en el estado de sesión.

Las pruebas sintéticas `tests/test_gemini_failover.py` no utilizan
la API real ni documentos privados.



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
