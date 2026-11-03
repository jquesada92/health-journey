# 08 — Harness de pruebas, criterios de aceptación y puertas de calidad

## Evidencia real de reparación histórica de fechas

Comprobaciones Neon después de la operación (2026-11-03):
`hj_extraction_audits`: 17 exámenes, 17 coincidencias
exactas entre timestamp y nombre, 0 desajustes,
17 fechas/hora únicas y 17 días distintos.
`hj_measurement_audits`: 1.087 filas; vista
`hj_audit_reviewed_private`: 1.087 filas;
`hj_exam_datetime_repair_history`: 17 entradas
con timestamp anterior y corregido, 17/17 iguales a
la tabla activa. Roles demo writer/runtime no tienen
SELECT sobre backup. Pruebas GitHub PR #89:
**424 passed, 1 warning** y harness aprobado;
las pruebas de CI NO sustituyen validación en HF.
El procedimiento de reemplazo por filename (010)
sigue pendiente, igual que su E2E.


## CA — fechas del reporte versus fecha del nombre

- Reporte de InBody `DD.MM.AAAA HH:MM` / con
  punto tras año debe convertirse a ISO SQL y, al
  faltar segundos, completar `:00` sin inventar hora.
- Después del primer `_` del nombre aceptar solo
  14 dígitos `AAAAMMDDHHMMSS` con fecha/hora reales.
  No buscar otros tokens del nombre ni adivinar.
- Si nombre y reporte difieren, prevalece nombre,
  conservar lectura IA original y segundos del nombre;
  si no hay timestamp en nombre, usar encabezado impreso.
- Un nombre inválido no debe corregirse silenciosamente
  con una fecha inventada.
- El usuario no debe cambiar arbitrariamente una
  fecha validada por nombre en el guardado.
- La reparación histórica 011 archiva primero fechas
  originales y actualiza sólo la cabecera auditada,
  conservando mediciones y filas originales; se
  debe revertir toda la operación si ocurre error.
- Tests sintéticos
  `tests/test_inbody_filename_timestamp.py`,
  `tests/test_exam_timestamp.py`. Validación real
  del Space y migración de datos pendientes.


## AC-V — reemplazo seguro por nombre de archivo (propuesta)

- Al cargar un nombre repetido, se bloquea la extracción salvo
  opt-in explícito; el usuario ve aviso de consumo de tokens.
- El opt-in no basta para editar a otro usuario: consulta privada
  de propiedad previa a Gemini, y nueva verificación al guardar.
- El único botón Guardar persiste solo filas `reviewed`, corrige
  valores originales auditables y usa `DATABASE_URL` privado
  para reemplazar por nombre; guardado normal sigue en
  DEMO_DATABASE_URL sin permisos de DELETE.
- SQL 010 exige confirmación, valida persona/archivo/hash y
  que no existan conflictos con otros archivos. Antes de
  eliminar filas activas, crea un backup completo. La
  transacción revertirá todos los cambios si falla el INSERT.
- Fecha y etiquetas no eliminadas de otros documentos.
  Una reingesta exitosa no duplica resultados; el historial
  InBody y el chat ven solo la versión nueva.
- Pruebas sintéticas de UI, derechos, payload, negativas,
  procedimiento SQL y contrato de rollback en
  `tests/test_inbody_filename_replacement.py`.
  E2E en HF/Neon requiere aplicación autorizada de SQL 010
  y prueba funcional manual.


## Regresión de formatos e inicio del Space

- Con 17 exámenes simulados y variantes `Body Fat
  Percentage`, `Percent Body Fat`, `Percentage of Body
  Fat`, el gráfico conserva los 11 puntos seleccionados:
  primera fecha y diez últimas, sin agujeros por diferencias
  de idioma o etiquetas.
- Reconocer `KG`, `kilogramos`, `pct`,
  `porcentaje`, inglés y español sin modificar el valor
  fuente ni la unidad almacenada.
- Convertir lb explícitas a kg **solo en visualización**;
  rechazar unidades ausentes, porcentajes expresados como
  ratio y nombres de segmentos anatómicos.
- Si hay valores duplicados por fecha y sección, priorizar
  la sección válida tanto en ES como en EN.
- `row_limits` no debe usarse en app.py mientras sea
  parámetro no implementado; el backend valida que existan
  filas antes del guardado.
- README conserva un YAML inicial correcto y fija Python
  3.12; CI y HF no garantizan ausencia de avisos del
  entorno, solo funcionamiento correcto de la app.
- Test: `tests/test_inbody_multilingual_trends.py`.
  Verificación de arranque y gráficas en navegador del
  Space permanece pendiente de despliegue.


## Regresiones para la alineación y fecha inicial del coach

- Los 11 slots seleccionados deben incluir la **primera prueba**
  y las diez últimas, aun cuando la primera sea de años antes.
- El eje es **ordinal** con tick inicial «1.ª DD/MM/AA» y tick
  final «Últ. DD/MM/AA», no una escala de tiempo implícita.
- Si una variable no está en la primera prueba, el primer slot
  debe quedar `None`, con anotación de ausencia y sin
  interpolación de datos inventados. Las otras medidas
  conservan su valor inicial disponible.
- El árbol AST de `app.py` debe tener dos columnas hijas
  directas de `hj-coach-layout`. El `Chatbot`, la caja
  de mensaje, controles y el encabezado deben pertenecer
  a la columna derecha, no salir de ella.
- CSS debe forzar dos columnas desktop y una móvil, y
  evitar min-width que provoque wrap.
- Tests sintéticos `tests/test_coach_first_last_trends.py`,
  además de CI; la prueba de aspecto real sigue pendiente
  al desplegar en Hugging Face.


## Aceptación: primera + diez últimas pruebas en coach

Con N fechas distintas en Neon, las cuatro gráficas usan
`{primera} ∪ {últimas 10}`, por fecha ascendente: N=1 implica 1
punto, N=10 implica 10, N=11 implica 11 y N=16 implica 11.
No se repite la primera, ni se muestran exámenes intermedios.
Los cuatro tipos de medida son independientes, no se inventan
ausencias y se conserva unidad: kg, kg, %, puntos. La consulta usa
permiso privado de servidor, identidad no visible y SQL
parametrizado antes de generar gráficas. Se valida el responsive
desktop/móvil, autocarga al abrir chat, botón manual de actualizar
y que no se alteran los turnos del chat. Fuente: vista auditada
revisada, con fallback confirmado heredado; límite seguro frente a
truncamiento. Regresión `tests/test_coach_first_last_trends.py`.
Verificación HF/Neon real después de desplegar: pendiente.


## Aceptación de entregables del Módulo 1 (propuesta)

1. La vista del proyecto ofrece ocho apartados en el orden del HTML docente, con textos editables y vista previa.
2. El pitch predeterminado contiene exactamente cinco frases; no se introducen pruebas de compañeros ni capturas supuestas.
3. `Generar Word (.docx)` descarga un DOCX real con los ocho apartados y hasta cuatro capturas con descripción, o marcas de evidencia pendiente.
4. No hay SQL ni envío a Gemini en el generador; se validan tipo, cantidad y tamaño de las imágenes.
5. La rúbrica (10/10/25/20/15/10/10 %) suma 100 % y se documenta en `docs/entregable-modulo1-obs.md`.
6. Tests: `tests/test_module1_deliverable.py`; dependencia `python-docx` y despliegue HF incluidos. E2E del Space y plantilla visual Blackboard son limitaciones pendientes.


## Contratos actuales y cobertura de CI · 2026-11-03

Se distinguen tres niveles: **(1) inventario/código estático**
(`harness/validar_reconstruccion.py`), **(2) pruebas sintéticas**
(`.github/workflows/test-inbody.yml`) y **(3) E2E HF/Gemini/Neon
real**, que continúa sin certificarse. La matriz F-01…F-15 y
AC-V-01…AC-V-12 se encuentra en
[00](00_estado_vigente_y_trazabilidad.md), con todos los módulos y
test files enumerados en [11](11_cobertura_codigo_main.md).

Contratos que CI debe proteger: cuatro módulos en el sidebar;
tres consentimientos `/privacy`; InBody
`Cargar → Extraer → Revisar → Guardar`, **solo Guardar mediciones**;
revisión `reviewed` obligatoria y originales inmutables;
comprobación de duplicado previa al uso de tokens;
historial FitNotes aislado por `owner_key`;
chat multiturno con prompts independientes y contexto InBody
automático sin ID visible; preservación de decimales y negativos.
En PR #84 se añade `tests/test_semantic_metadata.py` para el
catálogo ya existente en Neon y su lectura contextual con
límite de filas, alias y avisos de incertidumbre.

**Cobertura por archivo ≠ cobertura de ejecución al 100 %.** El
verificador ahora detecta rutas de funcionalidades agregadas sin
inventario; las pruebas unitarias que el workflow ejecute deben
listarse expresamente. Los 36 CA y diez CS que siguen son
**históricos**; no afirmar que están aprobados por su mera
presencia, y no exigir EasyOCR/CSV como UI principal.


---


> **Aceptación vigente (2026-11-03):** ver [AC-V-01…AC-V-12](00_estado_vigente_y_trazabilidad.md#3-matriz-de-aceptación-operativa), con pruebas, estado, pendientes y requisitos tecnológicos. Los **36 CA y 10 CS** conservados más abajo se preservan como visión/histórico porque el verificador de harness comprueba sus IDs: no se declaran aprobados automáticamente. Los criterios sobre EasyOCR, exportación CSV de siete columnas y selector CSV+Neon no son la UI principal de `main`. Las suites de CI son sintéticas (no Space real, Gemini o Neon); PR #72 para multiturno/prompts sigue sin fusionar y tiene 317 tests en su rama. Exigir evidencia visual móvil, E2E y aislamiento multitenant antes de dar por aceptado un lanzamiento.


**Normativa:** cada criterio debe tener resultado **APROBADO / FALLIDO / PENDIENTE / NO APLICA**, evidencia verificable (test, log saneado o captura anonimizada), commit y entorno. «El código parece soportarlo» no equivale a aprobado.

## 1. Estrategia de pruebas

1. **Unitarias offline:** extracción de texto, detección de plantilla/idioma, Pydantic, CSV, nombre de exportación, CSV múltiple y selección Plotly con entradas sintéticas.
2. **Integración offline:** Gradio y eventos con OCR/Neon simulados; no descargar modelos ni consultar recursos reales en CI.
3. **Integración PostgreSQL:** BD de QA efímera, migración, CRUD permitido, rollback de errores, duplicación, vistas y permisos mínimos. Jamás usar datos privados de producción.
4. **E2E de Space:** OAuth real, variables bien/mal configuradas, login autorizado/no autorizado, OCR con archivo sintético, exportación, guardado y consulta.
5. **Pruebas de compatibilidad:** dos o más plantillas, ES/EN, cambios de resolución, faltantes, valores ambiguos.
6. **Pruebas de seguridad:** rutas no autenticadas, manipulación de ID de persona, CSV con fórmulas y archivos adversariales, logs sin datos privados.

No agregar al repositorio informes reales; fixtures deben contener exclusivamente identidad y cifras ficticias.

## 2. Criterios funcionales comprobables

| ID | Dado / cuando / entonces | Evidencia requerida |
| --- | --- | --- |
| CA-01 | Dado PDF digital válido, al cargarlo se extrae texto sin necesitar OCR en la página legible. | Test PyMuPDF |
| CA-02 | Dado PDF escaneado, se invoca OCR y se registra página/método. | Test OCR simulado |
| CA-03 | Dado JPG y PNG válidos, se generan candidatos equivalentes al texto disponible. | Test tipos |
| CA-04 | Si contenido y extensión difieren, se rechaza antes de procesar. | Test adversarial |
| CA-05 | Si supera límites de tamaño/páginas/píxeles, se informa error controlado. | Tests límites |
| CA-06 | La extracción InBody 580 no confunde marcas de ejes con mediciones. | Fixture espacial |
| CA-07 | La plantilla ES con siluetas no mezcla piernas/brazos ni porcentajes de referencia. | Fixture ES |
| CA-08 | Impedancia 20/100 kHz en cinco regiones genera diez observaciones separadas cuando el fixture las contiene. | Test frecuencia |
| CA-09 | Una etiqueta no reconocida se conserva como dato pendiente. | Test parser |
| CA-10 | Dado encabezado claro español se captura `ES`; inglés `EN`; ambiguo `UNKNOWN`. | Tests idioma |
| CA-11 | Se puede corregir idioma, unidad, valor, variable y metadatos antes de confirmar. | Prueba UI |
| CA-12 | Sin hora comprobable no se inventa timestamp; sin DOB/edad no se inventa edad. | Test incertidumbre |
| CA-13 | El usuario puede exportar CSV **sin** `DATABASE_URL`. | Test app offline |
| CA-14 | El CSV mantiene exactamente las siete columnas y una fila por medida. | Test contrato |
| CA-15 | El nombre de cada exportación contiene hash de contenido + timestamp UTC del momento de exportar, sin PII. | Test nombre |
| CA-16 | Dos exportaciones sucesivas del mismo contenido generan nombres distintos sin sobreescritura. | Test colisión/repetición |
| CA-17 | Cargar varios CSV compatibles produce una tabla unificada sin tocar PostgreSQL. | Test con mock BD |
| CA-18 | CSV duplicados exactos no duplican las mediciones en el dashboard; informar omisiones. | Test dedupe |
| CA-19 | CSV inválidos (headers, UTF-8, valor no finito, extras, demasiado grandes) se rechazan o marcan sin ejecutar código. | Tests negativos |
| CA-20 | Una fila sin fecha aparece en tabla pero no crea un punto cronológico falso. | Test fechas |
| CA-21 | Al seleccionar fuente Neon se consulta solo tras autorización y se obtienen datos confirmados. | Integración/Space |
| CA-22 | Al cambiar la fuente del dashboard no se mezclan registros de CSV y Neon automáticamente. | Test aislamiento |
| CA-23 | Los filtros de persona, fecha, unidad, modelo, variable, segmento y frecuencia funcionan y muestran estado vacío correctamente. | Test UI/plot |
| CA-24 | Plotly dibuja líneas temporales por serie compatible; no une modelo, definición, unidad ni frecuencia distintos. | Test Plotly |
| CA-25 | Grasa kg, % de grasa, masa muscular esquelética y masa magra segmental se etiquetan separadamente. | Test semántico |
| CA-26 | El guardado Neon ocurre solo tras confirmación explícita y en una sola transacción. | Test integración BD |
| CA-27 | Reimportar archivo fuente de hash idéntico no inserta un segundo examen. | Test idempotencia |
| CA-28 | Error en una medida revierte toda la transacción; no quedan exámenes parciales. | Test rollback |
| CA-29 | El catálogo permite nuevas claves con etiquetas ES/EN sin nuevas columnas de tabla. | Test esquema |
| CA-30 | El histórico gráfico impreso no se registra como exámenes adicionales sin fechas verificadas. | Test plantilla |
| CA-31 | Gradio inicia desde `app.py`, sin importar Dash/Flask/React como UI. | Build/inspección |
| CA-32 | Cada módulo nuevo importado por `app.py` está incluido en la publicación del Space. | Test workflow |
| CA-33 | Space/BD desconectado: importación y visualización CSV continúan funcionando. | Test degradación |
| CA-34 | Un cambio de plantilla no rompe fixtures anteriores. | Regresión completa |
| CA-35 | La aplicación informa explícitamente si Guardar está deshabilitado; no desaparece silenciosamente. | Prueba UI |
| CA-36 | Ningún botón declara «guardado» antes de una respuesta positiva de la transacción. | Test error SQL |

## 3. Criterios de seguridad obligatorios

| ID | Condición | Evidencia |
| --- | --- | --- |
| CS-01 | Secretos nunca se imprimen ni se versionan; `.env` ignorado. | Revisión de repo + detección secretos |
| CS-02 | Usuario Space no autenticado/no autorizado no lee ni escribe en Neon. | Pruebas llamadas al backend |
| CS-03 | Cambiar parámetros manualmente no elude control de identidad; en multiusuario, comprobar propiedad por fila. | Prueba acceso cruzado |
| CS-04 | Rol Neon del Space carece de `DELETE`, `CREATEROLE` y membresía administrativa. | Consultas de privilegios |
| CS-05 | Todo tráfico PostgreSQL usa TLS y credencial de rol mínimo. | Config/validación conexión |
| CS-06 | Las páginas públicas/Space público no exponen informes de salud ni datos personales. | Revisión despliegue |
| CS-07 | Logs, CI, errores y métricas no muestran identificadores ni documentos originales. | Inspección de logs |
| CS-08 | Los uploads y CSV no se comparten entre sesiones y cumplen retención/limpieza. | Test aislamiento y limpieza |
| CS-09 | Importar CSV nunca escribe a Neon, aun si `ENABLE_PERSISTENCE=1`. | Prueba con spy SQL |
| CS-10 | Rechazar fórmulas CSV, valores infinitos, columnas extra y desbordes sin ejecución de código. | Suite maliciosos |

## 4. Casos de rendimiento / límites

- 1 PDF digital, 1 PDF escaneado, 1 JPG y 1 PNG sintéticos.
- 2 plantillas diferentes y 2 idiomas, una tercera desconocida.
- 25 CSV pequeños de ejemplo, con registros duplicados y fechas faltantes.
- 100 000 filas totales como techo inicial **objetivo**, ajustable tras medir memoria/CPU; no prometer capacidad real sin benchmark.
- Consulta paginada/limitada desde Neon; no cargar todas las personas al abrir el Space.
- Al fallar OCR/GPU, interfaz ofrece error claro sin guardar automáticamente datos parciales.

## 5. Comandos mínimos para CI

```bash
python -m compileall -q app.py inbody_mvp
python -m pytest -q tests
python harness/validar_reconstruccion.py
```

Los tests de integración Neon requieren una base efímera y secretos de CI específicos, nunca la base con datos reales.

## 6. Matriz de «Definition of Done»

Una historia se cierra solo si:
1. Contrato documentado y compatible con `harness/`.
2. Unit tests y regresiones sintéticas en verde.
3. Prueba manual anonimizada en entorno de despliegue correspondiente.
4. Seguridad y privacidad revisadas según exposición.
5. README/AGENTS/harness actualizados si cambia el diseño.
6. Migración o rollback disponible si cambia el esquema.
7. Evidencia del PR y un responsable que confirma la salida.

**Regla final:** el estado `PENDIENTE` de una prueba bloqueante no debe convertirse en `APROBADO` porque se creó un botón o una función.

## 7. Criterios experimentales de IA por secciones

**Importante:** el resultado de pruebas sintéticas confirma la lógica de
integración, **no** la precisión de PaddleOCR sobre los JPG personales.
Aplicar [el protocolo de evaluación](../docs/ocr-secciones-ia.md#7-evaluación-de-precisión-definir-primero-la-verdad-de-referencia).

| ID | Condición para aprobar | Estado inicial |
| --- | --- | --- |
| IA-01 | Detector real produce cajas válidas en muestras anonimizadas de varios modelos InBody | PENDIENTE |
| IA-02 | EasyOCR regional conserva coordenadas absolutas y etiqueta semántica con evidencia visual | PARCIAL — test sintético |
| IA-03 | Métricas por sección: valor, unidad, segmento y frecuencia coinciden con ground truth | PENDIENTE |
| IA-04 | Ningún eje ni punto del historial global es almacenado como examen actual | PENDIENTE |
| IA-05 | Fecha/hora del encabezado no se confunden con DOB; no se inventan valores | PENDIENTE en conjunto real |
| IA-06 | Layout + OCR supera baseline en exact match sin elevar falsos positivos críticos | PENDIENTE |
| IA-07 | Recursos de CPU/GPU, latencia p95 y compatibilidad de ZeroGPU verificados | PENDIENTE |
| IA-08 | Revisión humana, permisos, consentimiento y protección de datos no se degradan | PENDIENTE E2E |

Para comprobar IA-03 e IA-06 construir un ground truth privado para cada
uno de los 22 reportes de referencia: alias interno, modelo, sección, código,
unidad, valor, segmento, timestamp y posición. Revisar cifras directamente
de la imagen original; no utilizar resultados OCR como verdad de referencia.
Comparar baseline, modelo visual y un posible VLM **solo si éste se implementa**.
Registrar errores por sección y modelos incompatibles, además de promedios.

**No activar el modo experimental en producción ni considerar exactos los datos
de Neon hasta satisfacer los criterios de calidad y privacidad.**
