# Gemini Flash: revisión y auditoría por medición

> **Contrato actual contrastado (2026-11-03):** Gemini Flash devuelve `header` + `measurements` tipados; Python inyecta filename; la UI separa encabezado del cuerpo, conserva valor textual (`8.20`), original, correcciones y revisión, y permite guardar auditoría privada solo después de validación/consentimiento. Frecuencia e impedancia son mediciones independientes, no columna `frecuencia_khz`; no extraer historia impresa en el reporte. DDL versionado: migraciones 004–007 y funciones de idempotencia/confirmación de overwrite; comprobar aplicación real en Neon sin datos personales. El prompt de InBody está incrustado en `gemini_review.py` en `main`; su traslado a archivo propio es PR #72 abierto. [Mapa actual](../harness/00_estado_vigente_y_trazabilidad.md).



## Progress Dashboard — Gradio + Plotly (noviembre de 2026)

La pestaña **Progress Dashboard** sustituye el antiguo mensaje
«Dashboard (siguiente fase)». No incluye selector de examen: el sistema
selecciona automáticamente el valor más reciente disponible **por
variable** dentro del rango de fechas indicado. Filtros: ID de reporte
en campo privado (se normaliza al buscar), **Desde**, **Hasta** y una
sección para el análisis detallado. La interfaz muestra solo un alias
seudónimo, nunca la cédula InBody ni el nombre del archivo.

Plotly crea cinco indicadores `go.Indicator(number+delta)` y sus
flechas con variación porcentual relativa a la medición inmediatamente
anterior **de la misma variable y unidad**, dentro del intervalo:
`(actual - anterior) / abs(anterior) × 100`. Un aumento muestra ↑,
una disminución ↓ y un valor igual →. El color de la flecha es neutral,
ya que subir o bajar no determina por sí mismo un resultado de salud
favorable. Si no hay valor anterior o es cero, se muestra «Sin medición
anterior» o «Referencia anterior = 0», sin porcentaje inventado.

Métricas base: `Weight`, `Skeletal Muscle Mass`,
`Body Fat Mass`, `Body Fat Percentage` y `ECW Ratio`.
Un gráfico multieje de subplots Plotly conserva unidades separadas.
La tabla de histórico contiene fecha, variable, valor literal, unidad
y cambio; los valores como `8.20` se conservan como texto en tablas.

La subsección **Detailed Exam Analysis** permite elegir **sección**,
no un examen: toma la lectura más reciente de cada variable de esa
sección dentro del rango, muestra la lectura anterior, cambio relativo
y fecha. Las barras Plotly agrupan por unidad para evitar comparar
kg, porcentajes y otras magnitudes en un único eje. Las secciones nuevas
no reconocidas siguen apareciendo en «Todas las secciones».

**Fuente y límites:** la carga se realiza solo desde
`hj_audit_reviewed_private` en Neon mediante
`load_reviewed_audit_history`; requiere
`ENABLE_PERSISTENCE=1`, `DATABASE_URL`,
`HF_ALLOWED_USERS` y OAuth autorizado, incluso si
`ENABLE_ANONYMOUS_DEMO=1` permite escribir con consentimiento
y sin login. El dashboard público se mantiene aislado:
**guardar no significa autorizar publicación**.
El historial del gráfico embebido en el PDF nunca es una fuente.
La vista SQL retorna **fecha sin hora**; varias mediciones de la misma
variable en una misma fecha pueden ser ambiguas, por lo que no se
inventan promedios ni orden temporal intradía. El lector limita
la respuesta a 5000 filas, después de filtrar por identidad.

La implementación está en `inbody_mvp/progress_dashboard.py`, con
tests sintéticos `tests/test_progress_dashboard.py`. No se realizaron
migraciones adicionales ni se alteraron las auditorías guardadas.



## Identidad InBody: vinculación privada y seudónimo en consultas

Un ID numérico con separadores, por ejemplo `88571257` y
`8-857-1257`, se normaliza a la misma clave interna `88571257`
(sin espacios ni guiones; **sin quitar ceros iniciales**).
Para IDs alfanuméricos se conservan los separadores y se estandariza
el uso de mayúsculas. Nunca se utiliza el número del reporte, ni su
hash determinístico, como alias visible.

La migración 005 crea `hj_person_aliases`: clave canónica **privada**
y un UUID aleatorio persistente `anonymous_id`. Al insertar cada
auditoría, la función asigna el UUID de la persona; dos informes con
el mismo ID normalizado comparten alias. El ID tal como aparece en
el PDF sigue conservado solo en `hj_extraction_audits.person_id`
y en el JSON original de auditoría, sin acceso público.

La vista `hj_audit_reviewed_private` devuelve solamente UUID,
**fecha sin hora**, sección, medición, valor, unidad y estado de
corrección. Excluye `person_id`, `filename`, edad, hora exacta y
`raw_response`. Su acceso se limita a roles privados; en Gradio,
`load_reviewed_audit_history` exige OAuth antes de consultar.
El formulario recibe el ID real en un campo visualmente oculto
y muestra únicamente `Persona <alias>` en tabla/gráfica.

El rol `health_journey_demo_writer` conserva permiso de **ejecución
de la función de inserción**, pero ninguno de lectura de alias,
mapa de IDs o auditorías. El dashboard público **no** consulta
auditorías privadas automáticamente: consentir almacenamiento en
Neon no constituye consentimiento de publicación. Exponer
tendencias individuales requeriría un consentimiento separado
y una revisión del riesgo de reidentificación. Un UUID es
*seudonimización*, no garantía de anonimato absoluto.

La migración 005 fue **aplicada a la rama main de Neon health_journey el
1 de noviembre de 2026** tras probarla en una rama temporal con IDs
sintéticos equivalentes. Se confirmó que dos formatos del mismo ID se
vinculan al mismo UUID aleatorio, el rol `health_journey_demo_writer`
puede ejecutar la función de escritura y los roles de demostración
y público **no** pueden leer las auditorías ni los IDs privados.
La instalación SQL quedó verificada; la aplicación todavía requiere
variables y Secrets correctos, consentimiento, revisión completa y
comprobación funcional end-to-end en Hugging Face.



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
`ENABLE_ANONYMOUS_DEMO=1` (Variable HF). La migración
`migrations/005_consent_only_audit_writer.sql` **reutiliza** el rol
`health_journey_demo_writer` y no crea usuarios ni modifica contraseñas.
Solo concede permiso EXECUTE sobre la función de auditoría; el rol sigue
sin acceso directo de lectura o escritura sobre tablas privadas.

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


## Capturas repetidas y sobrescritura confirmada

La migración 007 detecta primero archivos ya procesados por nombre (sin diferenciar mayúsculas) o SHA-256. No los guarda de nuevo. Cuando coinciden ID normalizado, fecha-hora del examen y nombre de medición, solicita confirmación explícita antes de guardar otra versión. El dashboard privado presenta la versión más reciente, mientras el historial de auditoría anterior permanece intacto. Después de un guardado exitoso la interfaz limpia archivo, vista previa, tabla, estados y consentimientos. Si hay advertencia o error, conserva la revisión. El chequeo anticipado de nombres requiere sesión autorizada.


## Dashboard estilo InBody, Phase Angle e InBody Score

El **Dashboard único** presenta «Body Composition History» con filas
Plotly alineadas por fecha, inspiradas en el informe InBody original.
Muestra el valor impreso en cada punto, una línea por medición, la
última lectura y su cambio relativo en porcentaje con flechas ↑/↓.
Se conservan por separado las unidades y escalas de **Weight, SMM,
BFM, PBF, ECW Ratio y Phase Angle**. El último indicador admite
`Phase Angle` y `Phase Angle at 50 kHz` en °/grados, con nombres
ingleses estandarizados; las mediciones segmentales se excluyen
del KPI global. No se mezclan frecuencias distintas ni medidas
localizadas en extremidades. La sección detallada mantiene
comparación actual/anterior y añade tendencias históricas por
medición y unidad para la sección seleccionada.

El gráfico **InBody Score — progreso entre exámenes** es una línea
independiente, con valores, fechas y filtro temporal compartido.
Solo incluye los puntajes capturados y revisados de los exámenes
almacenados en Neon, **no** los puntos históricos dibujados en el
PDF. Si no hay puntajes registrados, muestra una figura vacía y un
mensaje informativo. No se inventan valores ni se interpretan las
flechas automáticamente como mejoras clínicas.

## Un solo popup cuando hay un error

Los errores de carga, vista previa, extracción Gemini, validación,
guardado, consulta Neon, consulta del Dashboard, cambio de
contraseña y diagnósticos de la API/GPU se muestran por
`gr.Warning` **una vez por evento**. No se escriben mensajes
de error en múltiples componentes y se conservan los valores
ya capturados o corregidos (`gr.update()`) para continuar.
Un guardado exitoso sí limpia el formulario y muestra un único
mensaje de éxito (`gr.Info`). Las advertencias de archivo
repetido o sobrescritura no autorizada tampoco vacían los
datos. No se exponen errores SQL internos, credenciales,
identificadores reales ni contenido del documento en un popup.


## Selector de modelos Gemini Flash (Free Tier)

En **InBody Upload** hay un menú desplegable de modelos
adecuados para leer el PDF/imagen y entregar las mediciones como JSON.
La aplicación consulta `client.models.list()` con la clave
`GEMINI_API_KEY` guardada como Secret; no manda ningún documento al
consultar los modelos. Interseca el resultado con esta lista de
**modelos cuyo nivel gratuito estándar está documentado por Google**
(consultada en noviembre de 2026):

- `gemini-3.8-flash`: recomendado para tablas y relaciones espaciales complejas.
- `gemini-3.6-flash`: alternativa multimodal.
- `gemini-3.5-flash-lite`: alternativa rápida y ligera.
- `gemini-3.1-flash-lite`: alternativa ligera.
- `gemini-2.5-flash` y `gemini-2.5-flash-lite`: modelos
  heredados; Google puede limitar su disponibilidad a proyectos con uso previo.

El menú solo enseña la intersección con los modelos **accesibles para
la API key**, y se actualiza automáticamente al entrar o con
«Actualizar modelos disponibles». Se prioriza el valor de
`GEMINI_MODEL` si aparece entre los accesibles; si no, se propone
`gemini-3.8-flash` cuando está disponible. Elegir un modelo cambia
solo la **siguiente extracción**; no modifica Secrets ni las
Variables del Space. El modelo efectivo (incluido el fallback 503)
queda registrado en el snapshot de auditoría. No se permite elegir un
modelo Pro, TTS, Live o de generación de imágenes.

**Advertencia:** que el proveedor anuncie **Free Tier** y liste un
modelo no prueba que el proyecto sea gratuito, que conserve cuota ni
que la facturación esté desactivada. En proyectos pagos puede haber
cargos; comprobar el nivel y límites reales en Google AI Studio.
Google también indica que los datos enviados en Free Tier pueden
usarse para mejorar sus productos. No subir resultados médicos
identificables a ese nivel sin revisar sus condiciones y consentimiento.

Fuente: https://ai.google.dev/gemini-api/docs/pricing y
https://ai.google.dev/gemini-api/docs/models

## Limpieza de herramientas del inicio

Se eliminaron de la UI principal los acordeones «Seguridad de la
cuenta (cambiar contraseña)» y «Diagnóstico ZeroGPU (opcional)».
**El inicio de sesión sigue habilitado**; el cambio de contraseña se
gestiona administrativamente y no aparece en el dashboard. Dado que
el Space utiliza hardware ZeroGPU, permanece un handler técnico
`@spaces.GPU` **invisible y sin endpoint público**, solo para
satisfacer el requisito de arranque; la extracción Gemini utiliza
la API de Google y no solicita GPU local.
