# 04 — Motor de extracción, OCR, plantillas e idioma


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
`AUDIT_DATABASE_URL` (Secret HF), usuario exacto
`health_journey_audit_submit`, SSL y
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


## Recuperación temporal de Gemini HTTP 503

La extracción usa el modelo configurado en `GEMINI_MODEL` y conserva el JSON
estructurado y la revisión por medición. El SDK oficial ya realiza reintentos
exponenciales ante 503. Si estos terminan sin éxito, la aplicación envía una
solicitud adicional a `GEMINI_FALLBACK_MODEL` (predeterminado:
`gemini-3.5-flash-lite`). No hay fallback ante 429, errores de
autenticación, esquema inválido o modelo inexistente. El fallback puede
desactivarse con `GEMINI_FALLBACK_MODEL=off`.

El modelo que produjo el JSON se conserva en `snapshot["model"]` y en
`hj_extraction_audits.model_name`; también se conservan
`primary_model` y `fallback_used` en el snapshot de sesión.
Toda medición debe revisarse, especialmente cuando se cambia a un
modelo de menor capacidad. La alternativa puede consumir cuota/costo.
Pruebas sin red: `tests/test_gemini_failover.py`.



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



## Contrato vigente de Gemini y auditoría (noviembre de 2026)

La respuesta Pydantic de Gemini contiene `header` (person_id,
exam_datetime, age), `measurements` (section, measurement, value, unit)
y `missing_or_unreadable`. Python obtiene `filename` del archivo original.
Cada una de las mediciones produce una fila con exactamente las columnas de
intercambio:

`exam_datetime, filename, person_id, age, section, measurement, value, unit`.

- `section`: sección del reporte, sin segmento corporal.
- `measurement`: etiqueta en español; para segmentos:
  `Brazo derecho - Masa magra`, `Brazo derecho - Frecuencia`.
- Frecuencia a 50 kHz: una fila de frecuencia (`50`, `kHz`) y
  otra fila de impedancia (`Brazo derecho - Impedancia a 50 kHz`, `Ω`).
- `Puntaje InBody` es una fila con unidad `puntos`.
- `value` permanece como **texto**, por ejemplo `8.20` y `0.370`.
- La fecha/hora es exclusiva del encabezado del examen actual;
  no se extrae información de `Body Composition History`.

**Auditoría separada, sin perder filas de origen:** `hj_extraction_audits`
conserva hash, filename, person_id, exam_datetime, age, modelo y JSON bruto.
`hj_measurement_audits` contiene una fila por medición, con
`original_section`, `original_measurement`, `original_value`,
`original_unit`, y sus versiones finales, `was_corrected`,
`correction_comment` y `reviewed_at`. Cuando una fila no cambió,
`was_corrected=false`; cuando cambió, requiere comentario. Las ocho columnas
se reconstruyen mediante join con la cabecera. **No es un cambio destructivo
de `hj_measurements` ni de la vista histórica de siete columnas**.

El nuevo contrato es el de Gemini y auditoría; las secciones siguientes sobre
el CSV de siete columnas describen compatibilidad *legacy*, no la salida
principal del InBody Upload. La migración SQL aditiva se encuentra en
`migrations/004_gemini_measurement_audit.sql` (distinta de
`db/migrations/004_anonymous_consented_demo.sql`).


## Estado vigente — 1 de noviembre de 2026 (PR #38, pendiente de validación E2E)

La interfaz activa de **InBody Hub** es Gradio y usa **Gemini Flash** mediante
`inbody_mvp/gemini_review.py` para extraer el examen actual de PDF/JPG/PNG.
El envío a Google exige consentimiento separado por documento. No se capturan
gráficos de historial. El encabezado (fecha/hora, archivo, ID y edad) se repite
en cada fila; `section`, `measurement`, `value`, `unit` forman el contrato
de mediciones. El nombre de la medición incluye el segmento corporal cuando
corresponde. Frecuencia es una medición por fila, y Puntaje InBody también.

La tabla permite revisar cada fila y corregir sección, nombre, valor y unidad.
Se conservan el valor original de Gemini, indicador calculado de corrección,
comentario obligatorio al corregir y estado revisado. Los decimales se
preservan como texto (ej. `8.20`). El guardado en Neon es una **auditoría privada**
separada de las tablas de historial y requiere OAuth, consentimiento y
`migrations/004_gemini_measurement_audit.sql`. No está comprobado el
despliegue E2E ni ejecutada esa migración.

**Componentes retirados del runtime/despliegue:** visor y editor de secciones,
EasyOCR, PaddleOCR y ZeroGPU. Los módulos y pruebas de OCR heredados permanecen
en el repositorio como material legacy; no se distribuyen en el Space. La
demostración anónima y el CSV antiguo no son parte del flujo activo de carga,
aunque subsisten módulos de compatibilidad y el dashboard público/historial.
No confundir documentación histórica del MVP con su estado operativo actual.


## 1. Entradas soportadas

- PDF digital: texto nativo con PyMuPDF y lectura ordenada, manteniendo páginas.
- PDF escaneado: renderizado controlado de páginas + OCR por imagen.
- JPG/JPEG/PNG: PIL/EXIF para orientación y verificación de tamaño, después EasyOCR.
- Rechazo de extensiones renombradas, archivos corruptos, protegidos por contraseña, sin contenido, demasiado grandes o con páginas excesivas.

La capa Python debe producir objetos Pydantic con `Measurement` y `ExtractionResult`, independientes de la UI. Un test nunca debe necesitar servicio externo ni informe personal identificable.

## 2. Problema de las tablas InBody

Los informes tienen tablas, barras, ejes con cifras de referencia, siluetas corporales, columnas segmentales, bloques superpuestos y valores sin unidad repetida por celda. **Extraer texto en orden lineal no basta**.

Reglas:

1. EasyOCR devuelve `detail=1`: texto, confianza y caja delimitadora. Conservar (x, y, ancho, alto), posición/página y fuente de OCR.
2. Normalizar coordenadas respecto al tamaño de página; aplicar cada parser **solo si identifica su plantilla** con señales suficientes.
3. Las cajas de resultado deben excluir ejes, límites de referencia y etiquetas que no son valores observados.
4. Conservar signos negativos en control de peso/grasa; no insertar un signo basándose en una expectativa.
5. No completar valores perdidos mediante resultados de otras regiones o exámenes anteriores.
6. La fuente OCR es un **candidato**; toda extracción densa requiere revisión visual, especialmente cifras pequeñas y ángulo de fase.

## 3. Clasificación por plantilla

| Familia | Archivo/política | Cuidado especial |
| --- | --- | --- |
| InBody 580 identificado | `inbody_mvp/layouts.py` | Tablas independientes, unidades, porcentajes de referencia y fase segmental |
| Plantilla en español con siluetas | `inbody_mvp/layouts_es.py` | Disposición segmental y 20/100 kHz; no deducir modelo sin evidencia |
| Otras | `inbody_mvp/extractor.py` parser conservador | Mantener desconocidos, no aplicar coordenadas fijas de otra plantilla |

Una plantilla InBody 580 puede aparecer en inglés u otro idioma; **modelo** y **lengua** son campos separados. El idioma determina traducción de etiquetas, no identidad del dispositivo.

## 4. Detección del idioma

`idioma_reporte` acepta exactamente `ES`, `EN` y `UNKNOWN`. Detector actual: `inbody_mvp/language.py`, con búsqueda conservadora de **varias** señales independientes en encabezados y métricas; no asumir idioma por país, edad, cédula o nombre de archivo.

Ejemplos de señales:

- `ES`: «Análisis de la Composición Corporal», «Masa Muscular Esquelética», «Porcentaje de Grasa Corporal».
- `EN`: «Body Composition Analysis», «Skeletal Muscle Mass», «Percent Body Fat».
- `UNKNOWN`: solo «InBody 580», OCR ilegible, una sola señal o señales contradictorias.

El usuario puede corregir el idioma antes de guardar. Persistir la selección revisada en `hj_exams.idioma_reporte`, preservando original de cada etiqueta en `hj_measurements.original_label`. La categorización y el código de medición son independientes del idioma.

## 5. Metadatos del examen

- `id_persona`: ID del reporte; no dar por sentado que es documento nacional verificado.
- `modelo_inbody`: solo si es legible o confirmado por el usuario.
- `timestamp`: fecha y hora; si el reporte solo incluye fecha, dejar hora pendiente. No atribuir zona horaria si no consta.
- `edad`: calcular desde nacimiento y fecha de examen únicamente si ambas son inequívocas y válidas; en otro caso permitir «reportada por el informe» o desconocida.
- `source_sha256`: hash de **archivo original** para control de duplicados (diferente al hash de contenido del CSV exportado).
- `archivo/tipo/página`: metadatos de origen; evitar conservar datos personales en logs.

## 6. Desambiguación de métricas

- `segmental_lean_mass` ≠ `skeletal_muscle_mass`.
- `body_fat_mass` (kg) ≠ `body_fat_percentage` (%).
- «Porcentaje segmental 97 %» puede ser porcentaje frente a referencia; **no** implica que el segmento tenga 97 % de músculo.
- «Impedancia 20 kHz / 100 kHz» debe producir filas diferentes por segmento+frecuencia.
- «Ángulo de fase» puede referirse a cuerpo completo o un segmento. No inferir 50 kHz como valor por defecto.
- En datos desconocidos, registrar etiqueta, valor, unidad y `sin_clasificar` en lugar de descartar.
- El historial gráfico impreso en el reporte no puede convertirse en exámenes históricos sin un parser explícito y fechas verificadas.

## 7. Criterios de aceptación específicos

- **OCR-01:** dado PDF digital sintético con varias métricas, se extraen texto, fecha, metadatos y candidatos sin OCR obligatorio.
- **OCR-02:** dado PDF escaneado sintético, se invoca OCR y se conserva referencia de página.
- **OCR-03:** dado imagen válida y lector OCR simulado con cajas, las medidas se asignan a celdas sin interpretar ejes como resultados.
- **OCR-04:** para plantilla ES con impedancia a 20/100 kHz y cinco regiones, 10 candidatos distintos y correctos cuando aparecen en fixtures.
- **OCR-05:** un archivo con nombre `.png` pero firma PDF es rechazado.
- **OCR-06:** ausencia de fecha/hora o unidad no produce valores inventados.
- **OCR-07:** no se capturan fechas/medidas del gráfico de historial como examen vigente.
- **OCR-08:** una plantilla no reconocida produce advertencias y/o extracción conservadora, sin aplicar coordenadas arbitrarias.
- **OCR-09:** ES/EN/UNKNOWN se determina conservadoramente y puede corregirse en la UI.
- **OCR-10:** comparar resultados reales anonimizados con un conjunto anotado manualmente; documentar precisión y falsos positivos por plantilla antes de afirmar soporte completo.

## 8. Nuevas plantillas: protocolo de incorporación

1. Crear fixture sintético de dimensiones similares con rótulos y cifras ficticias; nunca registrar un reporte real.
2. Anotar regiones normalizadas, encabezados distintivos, unidades y semánticas.
3. Implementar detector específico y extractor con salida `Measurement` común.
4. Probar variaciones de resolución, OCR que fragmenta/une textos, comas decimales y referencias en ejes.
5. Probar que **no** detecta otras plantillas por error.
6. Realizar prueba manual en entorno privado con consentimiento y anonimización, anotar límites y crear regresiones **sintéticas**.
7. Mantener soporte previo y no degradar los tests existentes.

## 9. Detección visual de secciones antes de OCR (experimento)

**Documento de referencia obligatorio:** [Arquitectura de IA por secciones](../docs/ocr-secciones-ia.md).

La visión por computador no interpreta automáticamente las mediciones de
salud. El prototipo `inbody_mvp/section_ai.py` usa un modelo preentrenado
`PP-DocLayout-S` para proponer **rectángulos genéricos de tabla/texto/gráfico**
y después vuelve a aplicar EasyOCR en recortes. La **clasificación semántica**
actual utiliza los títulos textuales de las regiones, no un VLM ni un
clasificador InBody entrenado con nuestros reportes.

**Contrato de salida:** conservar por medición la sección de origen, etiqueta,
posición y confianza OCR; antes de cerrar la implementación, extender los
modelos para evidenciar `section`, `source_bbox` y `extraction_method`.
No confundir probabilidad de detección de una región con certeza de un valor.

**Estado real:** la IA es opcional (flag `ENABLE_AI_SECTION_OCR`
desactivado). La reconciliación agrega o mejora tokens por posición y confianza,
pero la extracción de métricas sigue dependiendo de parsers preexistentes.
La exclusión del OCR regional de `history` aún **no elimina de manera
exhaustiva las cifras históricas del OCR global**. No declarar este criterio
cumplido sin pruebas específicas.

**Próximo diseño:** convertir los parsers a entradas explícitas por sección,
separar encabezado y cada tabla, y bloquear cualquier valor que dependa de ejes
históricos o corresponda a una unidad/segmento diferente. Evaluar un VLM
documental solamente después de comparar el baseline con layout + OCR.
Nunca publicar ni guardar sin revisión y consentimiento.
