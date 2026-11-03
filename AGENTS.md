# Reglas prioritarias de agente — GitHub main 2026-11-03

## Reingesta segura InBody por nombre de archivo (propuesta 2026-11-03)

Sin opt-in, el preflight de duplicados **bloquea** volver a gastar tokens.
Un archivo existente se puede volver a subir con el checkbox
`gemini_replace_existing`, que debe comenzar en false y comprobar
autorización de identidad **antes de Gemini**. Tras completar la tabla
y revisar cada `reviewed`, el único botón `Guardar mediciones`
invoca `save_audit(..., replace_filename=True)` por la conexión
privada `DATABASE_URL`, no por `DEMO_DATABASE_URL`. El nuevo
procedimiento `hj_replace_reviewed_audit_filename` sólo es
ejecutable por roles privados y compara nombre y persona; archiva
el original, borra exclusivamente filas activas del nombre elegido,
vuelve a validar e insertar la captura corregida **en la misma
transacción**. Un fallo hace rollback de todo. No extender el
permiso al demo writer ni a PUBLIC. El nuevo SQL 010 **NO está
aplicado en Neon** durante este PR: desplegar solamente tras
aplicarlo por una persona autorizada.

Conservar `source_sha256`, el payload original y los comentarios
de corrección en backup privado. No usar `DELETE` directo fuera
del procedimiento ni cambiar la vista privada auditada en otro
commit. No permitir sobreescritura si el nombre coincide con otro
usuario, si el documento pertenece a otro nombre o hay métricas
del mismo examen asociadas a otro archivo. Tests:
`tests/test_inbody_filename_replacement.py`; inventario
`harness/11_cobertura_codigo_main.md`.


## Normalización y arranque HF (2026-11-03; propuesta)

En `inbody_mvp/progress_dashboard.py` se usan alias explícitos
de medidas, idiomas y unidades para visualización, sin alterar
`value`, `original_value` ni Neon. La lista de etiquetas debe
reconocer `Percentage of Body Fat`, `Percent Body Fat` y
`Body Fat Percentage` como una sola métrica; no convertir
unidades faltantes, ratios desconocidos ni regiones segmentales
en valores totales. Solo convertir libras a kg cuando la unidad
original sea explícita y conservar trazabilidad en la copia
de la gráfica. Mantener pruebas con los tres nombres,
secciones ES, unidades y fechas faltantes.

El YAML frontal de `README.md` especifica Python 3.12 para HF,
igual que CI. El `gr.Dataframe` de revisión no debe usar el
parámetro `row_limits` mientras Gradio indique que todavía
no está implementado; `save_audit` valida los registros
conservados y rechaza la tabla vacía. Los avisos de root pip
y las excepciones `BaseEventLoop.__del__` en Python no prueban
por sí solos una falla de arranque. No ocultar excepciones reales
ni modificar `asyncio` por el log de limpieza sin reproducirlo.
Prueba: `tests/test_inbody_multilingual_trends.py`.


## Ajuste vigente propuesto: tendencias del Coach alineadas (2026-11-03)

En `inbody_mvp/coach_chat_ui.py`, el layout de tendencias y chat debe
usar una cuadrícula CSS `#hj-coach-layout` con dos columnas en
escritorio (gráficas izquierda, chat derecha), una columna en móvil
hasta 900 px. Los `gr.Column` de `app.py` deben ser hijos directos
del `gr.Row`, con `min_width=0` para impedir el wrapping automático
de Gradio. Todo el header, controles, `Chatbot` y composer debe
permanecer dentro de `hj-coach-conversation`.

En `inbody_mvp/coach_trends.py` mostrar las 11 fechas seleccionadas
(primera + diez últimas) como posiciones ordinales, etiquetar
primera/última y destacar la primera con marcador. Las fechas
intermedias no aparecen, los gaps entre fechas NO son temporales
en el eje. Si falta una medida en una de las fechas, conservar
el hueco `None`; nunca fabricar un valor. El estado del panel
indica la primera fecha registrada y la última. No alterar el
permiso privado ni invocar Gemini al cargar tendencias. Prueba
`tests/test_coach_first_last_trends.py`.


## Coach: regla de 1.ª + 10 últimas pruebas para tendencias compactas

`inbody_mvp/coach_trends.py` carga en lectura privada InBody
**primera fecha de examen + las 10 últimas fechas**, ordenadas
cronológicamente, deduplicadas y sin límite temporal del chat Gemini.
No limitar filas antes de elegir fechas, ni sustituir la primera por
una fecha dentro de los últimos 365 días. Los cuatro mini-gráficos
(peso, músculo esquelético, % grasa corporal, InBody Score) se muestran
a la izquierda del chat en `app.py` y encima en móvil. Respeta
`require_database_access` y la identidad privada resuelta en servidor;
no envíes nuevas consultas ni datos al LLM al actualizar gráficas.
Si las fuentes solo registran fecha, dos exámenes el mismo día se
consolidan visualmente en un punto por métrica y fecha; nunca inventar
horas ni valores. Las correcciones se leen de la vista revisada;
mediciones confirmadas legadas solo si no hay auditoría. Un límite
anti-truncamiento impide tendencias visuales parciales.
Contrato: `tests/test_coach_first_last_trends.py`; control en
`harness/11_cobertura_codigo_main.md`.


## Entregables académicos Módulo 1 (propuesta en PR)

El archivo `docs/entregable-modulo1-obs.md` es el contrato derivado de la consigna HTML proporcionada por el alumno, y `inbody_mvp/module1_deliverable.py` genera un DOCX real de ocho apartados desde la vista Proyecto, sin Gemini/Neon. El usuario revisa texto, completa el nombre y agrega cuatro capturas; ninguna prueba de terceros o evidencia ausente se inventa. Mantener los tests `tests/test_module1_deliverable.py`, dependencia `python-docx`, archivos de deployment y matriz `harness/11_cobertura_codigo_main.md` sincronizados.


Revisar primero [harness/00](harness/00_estado_vigente_y_trazabilidad.md)
y [harness/11](harness/11_cobertura_codigo_main.md). Cada archivo
`app.py`, `inbody_mvp/**`, `tests/**`, `docs/**`,
`migrations/**`, `db/**`, `sql/**`, workflows y archivos
raíz de producto debe figurar en el inventario 11. Al agregar
uno, actualizar su descripción y criterios en **el mismo PR**;
el verificador CI fallará si no hay enlace documental.

Versión real: cuatro módulos, InBody de cuatro pasos con **único
Guardar mediciones** tras `reviewed`, chat Gemini con prompts
independientes y lectura privada automática InBody/FitNotes, permisos
previos al login. No reintroducir validación duplicada, CSV/legacy
ni campo ID en coach. SQL 009 de metadatos está aplicado en Neon,
pero su lector `semantic_metadata.py` está en PR #84 hasta merge.
No afirmar E2E aprobado por CI; aislamiento multitenant InBody es P0.
Las notas de cronología que dicen 5 pasos/PR #72 abierto más abajo
son **ARCHIVO HISTÓRICO**, nunca requisitos actuales.

---

## Contexto semántico privado para Gemini (2026-11-03)

Neon cuenta con la migración 009 aplicada en main. Utilizar
`hj_measurement_catalog` para significado, unidad de referencia,
comparabilidad y precauciones, `hj_measurement_aliases` para nombres
equivalentes del mismo concepto, y `hj_ai_field_dictionary` como glosario
de columnas no sensibles. **Ninguna de estas tablas concede acceso a
mediciones personales**. La lectura ocurre en
`inbody_mvp/semantic_metadata.py`, después de verificar el propietario
privado, antes de la llamada consentida a Gemini. El contexto es solo
metadata de conceptos encontrados, jamás un dump del esquema, la
cédula, owner_key, comentario o OCR. Respetar `available` y
`truncated`, máxima cantidad de conceptos y privacidad del modelo.
Al introducir nuevas variables InBody, agregar catálogo y alias en
una migración aditiva idempotente. Tests:
`tests/test_semantic_metadata.py`, `tests/test_coach_auto_data.py`.
La versión en Hugging Face no cambiará hasta integrar y desplegar PR.

## InBody: un único botón Guardar mediciones (2026-11-03)

El flujo actualizado tiene cuatro pasos: **Cargar → Extraer → Revisar →
Guardar**. El usuario edita la tabla, marca cada fila `reviewed`, y
el único botón **Guardar mediciones** realiza reconciliación nativa,
validación exhaustiva y persistencia consentida; no existe botón
intermedio `Guardar cambios` ni etapa separada Validar. El cambio de
`value` determina `was_corrected`, `original_value` no se edita,
y una corrección requiere comentario. Errores no vacían datos ni
anulan consentimientos. Al guardar, se limpia la captura y se
reinicia la navegación. No confundir el consentimiento de Gemini
con el de Neon. `render_inbody_flow` usa cuatro pasos y el
panel del documento debe permanecer junto a la tabla.
Pruebas sintéticas: `tests/test_inbody_one_click_review.py`,
`tests/test_inbody_flow.py` y `tests/test_inbody_guided_layout.py`.
La documentación más antigua de cinco pasos es histórica, no el
contrato actual.

## Chat fitness automático con InBody y FitNotes (2026-11-03)

El chat ya no pide `coach_report_id`; no reintroducir filtros por
identificador manual. `inbody_mvp/ai_coach.py` carga, en cada pregunta,
InBody revisado y FitNotes del usuario autenticado; `coach_data.py`
resuelve internamente una identidad privada única (Secret
`COACH_PERSON_ID` opcional), incluye observaciones y series recientes
sin identificadores, y falla cerrado ante múltiples identidades.
La consulta FitNotes debe seguir restringida por `owner_key`, y la
consulta InBody debe seguir comprobando `require_database_access`.
Nunca enviar número de documento, archivos, notas, raw OCR ni comentarios
a Gemini. El prompt independiente `prompts/fitness_coach.md` documenta
el JSON y los indicadores de truncamiento. El deploy a Hugging Face
debe incluir explícitamente `inbody_mvp/coach_data.py`.
Pruebas `tests/test_coach_auto_data.py`, `tests/test_ai_coach.py`
y `tests/test_coach_conversation.py`; comprobar manualmente Space y
Neon antes de afirmar funcionamiento E2E.

## Ajuste vigente: confirmar tabla InBody sin repetición (2026-11-03)

El consentimiento prelogin firmado continúa siendo obligatorio para
contactar Gemini. El callback de extracción debe confiar en
`has_consent(request, "ai")` y no rechazar por una copia desactualizada
en `gr.State`. Pulsar **Guardar cambios** aprueba juntas todas las filas
conservadas **solo después** de validar las correcciones; no exigir
marcar `reviewed` en cada fila. Si falla la validación, conservar las
ediciones sin aprobarlas. El botón no autoriza transferencias a IA ni
escribe en Neon; esa escritura sigue requiriendo consentimiento de DB.
Consultar `tests/test_inbody_one_click_review.py`.

## Fuente vigente para ramas y PR (consolidación 2026-11-03)

Consultar [harness/00_estado_vigente_y_trazabilidad.md](harness/00_estado_vigente_y_trazabilidad.md) y [docs/indice_actual.md](docs/indice_actual.md) para capacidades, criterios, requisitos y tecnologías. Esta consolidación reúne las actualizaciones documentales del PR #73, correcciones de tabla InBody del PR #76 y verificación de duplicados antes de usar Gemini. No perder funcionalidades ya fusionadas (#71, #72, #74, #75). Cada PR posterior debe actualizar criterios, pruebas, documentación y limitaciones, distinguir CI sintético de prueba real de HF/Neon, mantener consentimiento y controles de acceso y evitar secretos o informes reales. No fusionar ni desplegar automáticamente.

## Prompts separados y conversación Gemini multi-turno (2026-11-03)

Health Journey guarda ahora las instrucciones de cada modelo en **archivos independientes**:
`inbody_mvp/prompts/inbody_extraction.md` para lectura de InBody y
`inbody_mvp/prompts/fitness_coach.md` para el coach basado en evidencia
(hipertrofia, fuerza, resistencia, composición corporal y recuperación).
El loader `inbody_mvp/prompt_loader.py` solo acepta dos nombres explícitos,
no rutas externas ni texto de usuarios. El prompt InBody conserva sus reglas
de mediciones exactas y JSON; el prompt fitness prohíbe inventar referencias
científicas, mediciones o diagnósticos. Los dos archivos se envían al Space
mediante la allowlist de despliegue.

El chat fitness utiliza un **historial canónico** en `gr.State` y presenta
la nueva burbuja del usuario inmediatamente, seguida de «Escribiendo…»,
antes de que Gemini responda. Una sola acción `gr.on` une clic en Enviar y
Enter, evita duplicaciones y deshabilita los controles mientras se procesa.
Si Gemini falla se conserva la pregunta, aparece una respuesta de error
en el mismo chat y los controles vuelven a estar disponibles. Cada mensaje
se muestra en orden; el historial visual no se trunca al recortar el
contexto del modelo (que conserva solo los turnos recientes para limitar
tokens). Al pulsar «Limpiar conversación» se borran estado y burbujas de
esta sesión, no datos de Neon.

`ai_coach.answer_coach_question` envía a Gemini `types.Content`
con los roles `user/model` de las intervenciones anteriores y la pregunta
actual en un nuevo turno. El archivo científico actúa como
`system_instruction` de la llamada; el JSON de InBody/FitNotes
sigue siendo información y NO instrucciones. **No incorpora un
buscador científico**, así que no afirmar referencias exactas sin
verificación. El selector Gemini sigue separado del extractor.

Comprobar `tests/test_coach_conversation.py`, `tests/test_ai_coach.py`
y `tests/test_coach_chat_ui.py`. Tras fusionar, validar en navegador
la secuencia de cuatro turnos, errores de API/cuota, Enter y Enviar,
limpieza del chat y móvil. No modificar consentimientos prelogin ni
guardar chats en Neon.

## UX InBody guiada con avance automático y limpieza tras guardar (2026-11-03)

Rama: `feature/inbody-auto-next-step-no-clear-20261103`. Solicitud más reciente:
retirar por completo el botón **«Limpiar examen (conservar permisos)»**,
desplazar la vista al próximo paso tras completar exitosamente el actual,
y que tras **guardar correctamente** la interfaz quede limpia y lista
para otro InBody.

Secuencia implementada: carga exitosa → paso 2; Gemini devuelve snapshot →
paso 3; el usuario marca todas las filas reviewed y pulsa
**Continuar a validación** → paso 4 (no desplazar durante edición);
validación completa → paso 5; guardado confirmado en base de datos →
`gr.Info` confirma, se limpian los 16 componentes del examen, mensaje de
guardado y estado del paso, y la vista regresa al paso 1. No limpiar tras
fallo de extracción/revisión/validación/guardado. El selector Gemini y
los tres consentimientos de sesión se conservan.

`INBODY_NEXT_STEP_JS` permite solo IDs `hj-inbody-step-1` a
`hj-inbody-step-5`, respeta accesibilidad y `scroll-margin-top` para
no ocultar secciones debajo de la navbar fija. No exponer datos personales
en el cliente. `review_step_ready` comprueba reviewed antes de avanzar,
pero la validación exhaustiva original permanece en `review_status`.
Los eventos `header_*.input` deben ser de usuario, NO `.change`,
pues limpiar campos desde el servidor reactivaba el paso 3.
Mantener el reinicio condicionado al guardado exitoso; conservar la
notificación emergente y limpiar el estado en línea.

Pruebas: `tests/test_inbody_flow.py` y
`tests/test_inbody_guided_layout.py` más CI completo. Requiere prueba
visual real en desktop/móvil y E2E con sesión autorizada antes de afirmar
que está desplegado.

## InBody: barra de progreso viewport-fixed (2026-11-03, corrige sticky)

La petición final exige que los cinco pasos **no se muevan al hacer scroll**;
`position: sticky` no cumplió el comportamiento esperado. La implementación
actual está en la rama `fix/inbody-viewport-fixed-navbar-20261103`.
`inbody_flow` es un HTML dentro de
`gr.Column(visible=False, elem_id="hj-inbody-fixedbar")`, creado en el
nivel superior del `gr.Blocks` para que ningún padre con scroll o
`transform` lo arrastre. Su CSS usa `position: fixed !important;
top: 0 !important`, con offset horizontal que respeta el contenido del
menú lateral (CSS anchors con fallback), y espacio superior reservado en
`#hj-panel-inbody`. El menú InBody pone visible el navbar; Proyecto,
Entrenamientos y Chat lo ocultan mediante `switch_module`, sin remontar
el `gr.HTML` ni alterar sus callbacks de estado. No introducir estilos
`display` que sobrescriban la visibilidad de Gradio.

Esto sustituye la instrucción anterior de no usar `position: fixed`.
No reconstruir la barra como hijo del panel desplazable. Mantener el
indicador compacto en móvil, verificar que no tape campos y confirmar
en navegador real el scroll, el sidebar colapsado y cambio de módulo.
Tests: `tests/test_inbody_flow.py`, `tests/test_inbody_guided_layout.py`
y `tests/test_sidebar_navigation.py`. Sin migración de Neon.

## UI InBody: diagrama al inicio absoluto del módulo y sin título global duplicado (2026-11-03)

Rama: `fix/inbody-top-sticky-progress-no-global-header-20261103`.
Por petición posterior a PR #67, el orden correcto **actual** es:
**indicador de 5 pasos → título de InBody → instrucciones → carga**.
Se eliminó la cabecera Markdown global `# Health Journey · Asistente
virtual de fitness y bienestar`, ya que el título principal figura en
`gr.Sidebar`. También se movió el acordeón de los tres consentimientos
dentro del Sidebar, **después de las cuatro opciones del menú** y cerrado
por defecto: no debe volver a aparecer como franja horizontal por encima
del diagrama. No eliminar los consentimientos firmados ni sus tres callbacks;
el usuario debe poder retirarlos durante la sesión. En móvil el menú
permanece plegable.

El indicador sigue anclado a `#hj-inbody-sticky` con CSS
`position: sticky; top: 0` limitado al panel InBody; no convertirlo en
`position: fixed` global porque tapa Proyecto/Entrenamiento/Chat.
No cambiar estados de progreso, Gemini, Neon ni datos. Las pruebas en
`tests/test_inbody_flow.py` y `tests/test_session_consent.py`
comprueban posición y controles; prueba visual real en Space pendiente.

## InBody: indicador de pasos debajo del título y visible durante scroll (2026-11-02)

Rama: `fix/inbody-sticky-progress-below-title-20261102`.
El orden del módulo debe ser **título de InBody → indicador de 5 pasos
→ instrucciones → carga de archivo**. El indicador usa un wrapper
`gr.Column(elem_id="hj-inbody-sticky")` y un HTML interno con
`elem_id="hj-inbody-flow"`. CSS sticky en el **wrapper persistente**,
no en una etiqueta que Gradio vuelva a renderizar. Se conserva
`top: 0`, `z-index: 50` y `overflow: visible` para no recortarlo.
No cambiar a `position: fixed`: debe mostrarse solo en el extractor
y desplazarse hasta salir de su sección. Compactar en móvil para que
no bloquee las mediciones. Los cinco estados siguen gobernados por
los callbacks reales y el permiso/guardado original no cambia.
Prueba: `tests/test_inbody_flow.py`. Sin despliegue validado.

## UI chat fitness tipo mensajería · 2 de noviembre de 2026 (PR pendiente)

La rama `feature/whatsapp-style-fitness-chat-20261102` introduce una
presentación visual inspirada en WhatsApp en **Chat con el asistente fitness**:
cabecera compacta, burbujas derecha/izquierda, altura flexible, compositor
persistente y diseño adaptable al celular. Las clases y colores están
aislados en `inbody_mvp/coach_chat_ui.py`, cargados mediante
`COACH_CHAT_CSS`; no modificar los componentes InBody ni el menú lateral.

**No hacer selector Gemini global:** el extractor conserva
`gemini_model_selector` y el chat usa su propio `coach_model`.
El acordeón de objetivos, restricciones y privacidad permanece opcional
y colapsado; el consentimiento de chat se sigue comprobando en el servidor.
Se preservan exactamente los callbacks existentes: enviar mediante botón
o Enter, actualizar modelos, mostrar resumen de datos y limpiar chat.
Gradio 6 usa mensajes con roles y `gr.Chatbot(layout="bubble")`; no
reintroducir el parámetro `type` eliminado. El chat sigue usando la
API Gemini Flash, no un modelo servido por Gradio.

La lista de archivos del Space incluye `coach_chat_ui.py` y CI ejecuta
`tests/test_coach_chat_ui.py`. El diseño no equivale a una validación
en navegador móvil o en el Space; comprobar visualmente antes de
declarar desplegado.

## Cambio en desarrollo · Menú simplificado, página Proyecto y chat fitness (2 noviembre 2026)

Rama: `feature/ai-coach-simplified-navigation-20261102`, **sin merge ni despliegue verificado**.
Las únicas secciones visibles en el menú lateral son, en este orden:
1. Proyecto (pantalla inicial después del login; motivación, propósito y stack).
2. Extractor de InBody.
3. Captador de logs de entrenamiento.
4. Chat con el asistente fitness.

No volver a introducir `gr.Tabs` horizontales, su overflow de tres puntos,
una sección independiente de Historial o un menú Dashboard. Se conserva el
dashboard de progreso en un acordeón dentro de InBody, y se conservan todos
los datos históricos en Neon. La nueva página Proyecto está en
`inbody_mvp/project_overview.py`, separada del README técnico.

El chat usa `inbody_mvp/ai_coach.py` y consultas privadas de InBody + FitNotes
que pasan por los controles de autorización existentes. El usuario introduce
ID del reporte InBody opcional, objetivos y restricciones. No se migran tablas
de Neon. El historial del chat y las metas no se almacenan automáticamente.
El permiso `coach` es **tercero e independiente**, con opt-in previo al login
en `inbody_mvp/prelogin_consent.py` y verificación de cookie firmada
en cada llamada. No compartir raw OCR, IDs, comentarios del entrenamiento,
documentos ni credenciales con Gemini. **Validación del PR #64 (2026-11-02):** CI de `Test InBody MVP` en el commit
`a6a37ee0` completado con **305 pruebas aprobadas**, `ruff F821`
y compilación Python correctas. El harness de reconstrucción también pasó.
Esto NO certifica ejecución de Gradio en Space ni una conversación real con Gemini.

No fusionar ni activar el chat en
producción multiusuario sin resolver antes la relación owner / persona InBody.
Los resultados son informativos, nunca diagnósticos ni prescripciones médicas.

Guía: `docs/ai-coach.md`; pruebas: `tests/test_ai_coach.py`,
`tests/test_sidebar_navigation.py`, regresión de Training Hub, dashboard y
consentimiento. Actualizar esta sección con evidencia real de CI, PR y
despliegue antes de afirmar que está activo.

## Propuesta Training Hub · FitNotes (2 noviembre 2026; NO desplegada)

Rama de trabajo: `feature/training-fitnotes-neon-import-20261102`.
Se añadió un módulo separado `inbody_mvp/training_hub.py` y pestaña
`Training Hub` en Gradio. Se procesan CSV FitNotes UTF-8 de 10 columnas
con límite 10 MiB/100.000 series, vista previa de 60, consentimiento
explícito, escritura transaccional y consulta privada. **La migración fue aplicada a Neon principal con autorización y verificada
(ambas tablas con cero filas); no se fusionó el PR ni se importó la data real.**
La migración aditiva `migrations/008_fitnotes_training_hub.sql` está
probada en rama temporal y aplicada a Neon principal el 2 de noviembre de
2026, con autorización expresa del usuario.

Se mantienen varias series idénticas como eventos distintos: el identificador
es propietario + fecha + ejercicio normalizado + número de serie en orden
de archivo. Cargas incrementales ignoran series sin cambios; diferencias
necesitan confirmación antes de sobrescribir. La huella SHA-256 evita
reprocesar el mismo archivo. Preservar decimales/negativos con Decimal,
no convertir ausentes en cero ni inventar timestamps. Nunca usar el
CSV personal del usuario como fixture ni exponer tablas a roles públicos.
Roles permitidos: `health_journey_app` y `health_journey_runtime`.
Validación: `tests/test_training_hub.py` y
`tests/test_training_ui_contract.py`. Detalles: `docs/training-hub.md`.

# AGENTS.md — Health Journey

## Infraestructura actual: Gemini Flash sobre Space ZeroGPU existente (2026-11-01)

El PR #38 ya fue fusionado en `main`. La extracción utiliza Gemini Flash
por API y **no necesita GPU** para procesar los InBody. Sin embargo, el Space
`jaqo/health-journey` sigue asignado a hardware **ZeroGPU** y el usuario
no dispone de CPU Basic en sus opciones de hardware. ZeroGPU exige una
función `@spaces.GPU` conectada a un evento de Gradio para superar el
control de arranque. La solución de compatibilidad es un **diagnóstico CUDA
opcional** asociado a un botón en un acordeón cerrado; no se usa en
`extract_gemini` ni en `save_audit`. Solo al pulsar el diagnóstico se
solicita GPU y se consume la cuota correspondiente.

`app.py` importa `spaces` y registra la función decorada antes de
construir la interfaz. `requirements.txt` mantiene `gradio[oauth]` y
`spaces`. No reinstalar EasyOCR/PaddleOCR para este workaround ni eliminar
el soporte ZeroGPU de la infraestructura hasta que haya otro hardware
disponible. Tras fusionar este PR, verificar el nuevo build del Space y
los flujos de extracción, revisión y consentimiento. Esta compatibilidad
no constituye una validación end-to-end.


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
EasyOCR y PaddleOCR. Los módulos y pruebas de OCR heredados permanecen
en el repositorio como material legacy; no se distribuyen en el Space. La
demostración anónima y el CSV antiguo no son parte del flujo activo de carga,
aunque subsisten módulos de compatibilidad y el dashboard público/historial.
No confundir documentación histórica del MVP con su estado operativo actual.


## Estado real y dirección técnica (31 de octubre de 2026)

Este repositorio implementa progresivamente **InBody Hub**, primera fase de Health Journey. **Gradio** es la única interfaz web del MVP: el punto de entrada es `app.py` y el Space usa `sdk: gradio` con ZeroGPU. **Pydantic** valida los datos, **PyMuPDF** extrae texto de PDF, **EasyOCR** procesa JPG/PNG y páginas escaneadas, y **Pandas** permite revisar/exportar. **Plotly** se reserva para un dashboard de tendencias integrado en Gradio (`gr.Plot`) en la siguiente fase.

**No desarrollar ni reintroducir Dash, Flask o React como interfaces.** Mantener `app.py` como entrypoint. No sustituir el SDK de Gradio ni romper ZeroGPU sin una necesidad técnica verificada y autorización expresa.

## Funcionalidad implementada

- Carga de **PDF, JPG, JPEG y PNG** desde `app.py` (límite 15 MB y 8 páginas para PDF).
- Extracción de texto digital con PyMuPDF; OCR EasyOCR para archivos escaneados e imágenes.
- Clasificación conservadora de mediciones conocidas; admite variables desconocidas, segmentos y frecuencias (por ejemplo, ángulo de fase).
- Revisión humana con `gr.Dataframe`; extracción, etiquetas, unidades y valores son **candidatos**.
- Exportación **CSV borrador** con siete columnas: `id_persona`, `modelo_inbody`, `timestamp`, `variable_medida`, `unidad_medida`, `valor_medida`, `edad`.
- Vista informativa de Dashboard futuro y pestaña Proyecto que muestra `README.md`.

**No implementado:** identificación verificada, confirmación persistente, base de datos, deduplicación histórica, autenticación, analítica longitudinal real, gráficas históricas, TrOCR o asistente virtual.

## Organización

- `app.py`: componentes y eventos Gradio; mantener la lógica de extracción separada.
- `inbody_mvp/extractor.py`: lectura PDF/imágenes, OCR de respaldo, Pydantic y clasificación inicial.
- `inbody_mvp/layouts.py`: interpretación conservadora de celdas por coordenadas para el formato InBody 580; no confundir ejes y porcentajes de referencia con mediciones.
- `inbody_mvp/review.py`: tabla de revisión, validación de ediciones, exportación CSV.
- `tests/test_inbody_mvp.py` y `tests/test_review.py`: pruebas unitarias.
- `requirements.txt`: dependencias de ejecución.
- `.github/workflows/deploy-huggingface.yml`: sincroniza `app.py`, `README.md`, `requirements.txt` y los módulos Python de `inbody_mvp/` con el Space `jaqo/health-journey`.
- `docs/despliegue-hugging-face.md`: instrucciones de despliegue.

## Principios de extracción y almacenamiento

1. **Una fila por medición.** Las nuevas variables se agregan como nuevas filas, nunca requieren nuevas columnas en la tabla analítica.
2. **Nada de datos inventados:** faltantes/ambiguos permanecen vacíos; no sustituir por cero ni suponer unidades o timestamps.
3. **Clasificación y dimensión independientes:** conservar etiqueta original, categoría, unidad, segmento, lateralidad, frecuencia y trazabilidad.
4. **Separar masa muscular esquelética de masa libre de grasa.** No equiparar porcentajes relativos a referencia con porcentajes de composición corporal.
5. **Ángulo de fase:** diferenciar cuerpo completo y segmentos, respetar frecuencia (kHz) si aparece; no suponer 50 kHz.
6. **Edad:** calcular desde fecha de nacimiento y fecha del examen si ambas existen; distinguir de edad transcrita.
7. **Identidad:** el ID del reporte no necesariamente es una cédula verificada; no mezclar personas.
8. **Comparabilidad:** no graficar como equivalentes mediciones de definiciones, modelos o frecuencias incompatibles.
9. **Privacidad:** jamás incluir documentos reales, IDs reales, datos médicos o secretos en repositorio, ejemplos, pruebas o logs públicos. QA público solo con archivos ficticios o anonimizados.

## Flujo de trabajo para agentes

- Leer `README.md`, `especificacion.md` y este archivo antes de modificar arquitectura.
- Implementar cambios pequeños y verificables. No declarar disponibles funciones que solo estén previstas.
- No publicar ni alterar credenciales; las claves de Hugging Face están en secretos de GitHub, no en el código.
- No desplegar, hacer merge ni push a `main` sin autorización del usuario.
- Preservar el encabezado YAML de `README.md`: `sdk: gradio`, `app_file: app.py`.
- Mantener separado el motor Python de la UI para poder extender el dashboard Gradio + Plotly sin reescribir la extracción.
- Antes de finalizar, ejecutar `python -m pytest -q tests/test_inbody_mvp.py tests/test_review.py tests/test_inbody_layouts.py` y revisar la compilación sintáctica.
- No afirmar que se ha validado el Space ni el OCR real con reportes auténticos si no hay pruebas de ello.

## Hoja de ruta

1. Completar y probar extracción en reportes InBody reales **anonimizados** de diferentes modelos, reforzar la clasificación y revisión.
2. Almacenar exámenes confirmados con trazabilidad, control de duplicados y acceso privado en PostgreSQL.
3. Crear **dashboard Gradio + Plotly**: filtros por persona, fecha, medida, unidad, región, segmentos (brazos, piernas, tronco), gráficas de líneas, grasa versus músculo y ángulo de fase (global/segmental/frecuencia).
4. Expandir posteriormente a módulos Training y Nutrition; Medical Hub requiere controles clínicos adicionales.

La documentación del reto OBS de semana 2 describe estados históricos y no debe confundirse con las capacidades actuales.

## Validación de formatos densos

- EasyOCR debe devolver `detail=1` para preservar coordenadas y texto; el resumen de texto sin posiciones no basta para tablas InBody.
- Para InBody 580 se usan celdas específicas en `inbody_mvp/layouts.py`; no aplicar esas coordenadas a equipos diferentes.
- No agregar reportes reales ni capturas con cédulas o datos médicos a los tests o al repositorio.
- Los resultados espaciales son candidatos no confirmados: validar visualmente números, signos, unidades, segmentos y porcentajes contra sus referencias originales.
- El historial impreso dentro de una hoja InBody no debe mezclarse automáticamente con el examen actual.

## Persistencia Neon y clasificación de idioma (implementación experimental)

- El proyecto Neon `health-journey` y la base `health_journey` existen con tablas `hj_persons`, `hj_exams`, `hj_measurements`, `hj_measurement_catalog` y vista `hj_measurements_long`. El DDL está en `db/schema.sql`; no ejecutarlo de manera destructiva.
- Clasificar `idioma_reporte` en `ES`, `EN`, `UNKNOWN` desde encabezados mediante `inbody_mvp/language.py`. Pedir revisión humana si no hay suficiente evidencia; el idioma se almacena por examen.
- La capa `inbody_mvp/storage.py` escribe las mediciones revisadas transaccionalmente; necesita `DATABASE_URL` TLS y `ENABLE_PERSISTENCE=1`. No leer ni imprimir credenciales, ni almacenar PDFs o imágenes reales en Git.
- **Prohibido activar guardar en un Space público** sin autenticación/autorización y controles específicos de información médica. En un Space, el código requiere configuración explícita, allowlist de usuarios y perfil OAuth verificado para cada acceso; esto no convierte automáticamente en seguro un Space público. No guardar información personal real sin controles de privacidad y acceso revisados.
- `hj_measurements_long` conserva siete columnas y no contiene `idioma_reporte`; el idioma y la etiqueta original se consultan en las tablas base. Nuevas métricas agregan filas y entradas al catálogo, no nuevas columnas.
- Los tests `tests/test_language_storage.py` no requieren conexión a Neon ni usan datos personales reales.
- Guía de operación: `docs/neon-postgres.md`.


## Harness de reconstrucción (normativo)

El directorio [`harness/`](harness/README.md) reúne en **español** la especificación canónica del producto, arquitectura, modelo SQL/CSV, diseño de OCR y dashboard, política de seguridad, runbook de reconstrucción, decisiones, 36 criterios funcionales y 10 de seguridad. Antes de introducir cambios, consultar el harness y mantenerlo actualizado; distinguir estado verificado de requisitos aún pendientes. Ejecutar `python harness/validar_reconstruccion.py` en cada PR que afecte contratos o estructura.

**Requisitos nuevos aún por completar según el estado de `main` al 31/10/2026:** nombre de exportación CSV con hash de contenido + timestamp UTC, y dashboard con elección entre Neon y carga múltiple de CSV sin persistencia automática. No reintroducir Dash.

## Restricciones del dashboard público

La modalidad pública es **solo estadísticas agregadas**, nunca registros por persona: la vista `hj_public_monthly_summary` usa únicamente exámenes explícitamente aprobados, agrupa por mes/modelo/métrica/unidad/segmento/frecuencia y suprime grupos de menos de cinco participantes. No expone ID, fechas exactas ni edad.

**Contrato actualizado: Space único.** En el mismo Gradio Space se permiten OCR, CSV y consulta de estadísticas/series públicas, independientemente de `ENABLE_PUBLIC_DASHBOARD`. El backend puede recibir dos secretos distintos: `DATABASE_URL` para operaciones privadas con OAuth y `PUBLIC_DATABASE_URL` solo para la lectura de vistas autorizadas con rol `health_journey_public`. Mantener validación OAuth por llamada en operaciones privadas de Neon; nunca exponer los datos de identidad mediante el lector público. Para OCR anónimo en un Space público solo se admiten documentos previamente anonimizados. Ver `docs/dashboard-publico.md` y `docs/public-person-series.md`.

## Flujo de autenticación simplificado

La extracción OCR, revisión y exportación CSV no requieren OAuth ni conexión Neon, pero **solo se permiten reportes sintéticos o anonimizados** si el Space es público. Se eliminó la sección superior de «Login / Comprobar sesión»; los controles de login quedan dentro de «Acceso privado a Neon» cuando el servicio está configurado.

Las lecturas y escrituras privadas de Neon **siguen exigiendo** OAuth con `OAuthProfile.username` y `HF_ALLOWED_USERS` validado en servidor. No desactivar esta comprobación. `ENABLE_PUBLIC_DASHBOARD=1` activa el lector público pero **no bloquea** OCR, CSV ni los controles privados. La ausencia de login en OCR no significa que sea seguro subir informes identificables a un Space público.

## OAuth robusto: evitar pantalla blanca de login en iframe

Para operaciones privadas de Neon, el Space presenta un enlace de login en pestaña nueva basado en `SPACE_HOST` validado y `/login/huggingface`, que evita problemas de cookies en la aplicación incrustada. Mantener `hf_oauth: true` y `gradio[oauth]`. No insertar credenciales en URLs, archivos o logs, ni construir hosts desde un ID sin verificar. El componente nativo `gr.LoginButton` puede existir oculto como respaldo para registrar OAuth y solo mostrarse cuando el Space no provea un `SPACE_HOST` válido. Guardar/consultar Neon **siempre** exige `OAuthProfile.username` permitido. `inbody_mvp/oauth_ui.py` y `tests/test_oauth_standalone.py` definen y verifican este contrato.

## Excepción de demostración académica con escritura anónima

`ENABLE_ANONYMOUS_DEMO=1` permite probar el flujo **sin OAuth** únicamente mediante un rol SQL **aislado y restringido**: `DEMO_DATABASE_URL` conecta como `health_journey_demo_writer`, con permisos EXECUTE únicamente sobre las funciones validadas `hj_submit_demo_report` y `hj_submit_reviewed_audit` (migraciones 004 y 005), **sin permisos directos SELECT/INSERT/UPDATE/DELETE sobre tablas privadas**. La función SQL valida esquema, tipo, unidades y cantidad de mediciones, y aplica cuota de solicitudes. El UI exige consentimiento de almacenamiento y, por separado, autorización de publicación; ambos son falsos por defecto. Los registros publicados se exponen desde `hj_demo_public_series` con alias aleatorio y fecha sin hora, sin ID real, nombre, edad, fuente u OCR; expiración visible de siete días. En demo los controles de consulta de históricos privados y login están deshabilitados/ocultos. El flujo de extracción Gemini requiere consentimiento independiente; guardar auditoría requiere consentimiento para Neon, pero no OAuth y usa el mismo flag `ENABLE_ANONYMOUS_DEMO`, nunca `ENABLE_ANONYMOUS_AUDIT`. La lectura del historial privado sí exige `require_database_access` y OAuth. No confundir almacenamiento con autorización de publicación. **No dar permisos INSERT en `hj_exams` al rol demo.** Ver `docs/demo-anonima-consentimiento.md` y migración 004. Subir solo documentos previamente anonimizados a un Space público.

## Contrato de fecha de examen automática

El timestamp siempre procede del documento original vía `ExtractionResult.timestamp`. `app.py` presenta fecha/hora solo lectura, pero **CSV y guardado no deben aceptar el Textbox como entrada de confianza**: recuperan `source_exam_timestamp(extraction_state)`. `prepare_confirmed_exam` verifica que el valor recibido coincida con el extraído. Admitir etiquetas «Fecha», «Fecha de examen/medición», «Test Date», «Measurement Date» y «Date of Test» con hora explícita, sin confundir fecha de nacimiento o usar la fecha actual. Si falta fecha u hora, no inventar ni admitir edición manual: informar al usuario y bloquear exportación/guardado, sin alterar métricas. Mantener regresiones en `tests/test_exam_timestamp.py`.

## Regresión de encabezados de fecha/hora en dos líneas

Requisitos comprobables adicionales: aceptar `Test Date / Time\n04.10.2026. 10:04` y `Fecha / Hora del test\n26.01.2025. 14:20` del encabezado InBody (etiqueta y fecha/hora en líneas distintas, punto de cierre después del año). No utilizar una fecha de nacimiento, un gráfico histórico, una fecha sin hora, un reloj inválido ni la fecha actual como sustitutos. Mantener pruebas en `tests/test_exam_timestamp.py`. En un reporte con OCR posicional, la fecha extraída de la región de encabezado debe seguir teniendo precedencia.

## Timestamp InBody: resolver columnas OCR por coordenadas

Para ambos encabezados reales `Test Date / Time` y `Fecha / Hora del test`, **el OCR de texto plano NO es suficiente**: `tokens_to_text` puede poner `Gender`/`Género` delante del título y la fecha de nacimiento antes de la fecha del examen. El extractor `extract_header_exam_timestamp` en `inbody_mvp/layouts.py` toma la fecha y hora directamente de detecciones EasyOCR con posiciones del encabezado superior y su propia columna de examen, exigiendo un título explícito y valores en el mismo renglón. No acepta fechas del DOB ni valores del historial. `extract_document` usa ese timestamp para ambos tipos de plantilla, y nunca lo debe borrar al reconocer siluetas españolas. No se guardan imágenes reales ni identificadores en tests; mantener `tests/test_header_spatial_timestamp.py` y las otras pruebas de fecha. Comprobar el despliegue real con reportes del propietario, sin ponerlos en GitHub.

## IA para seccionar los InBody: contrato obligatorio y límites

**Referencia para cualquier cambio:** [docs/ocr-secciones-ia.md](docs/ocr-secciones-ia.md).
La IA actual (`inbody_mvp/section_ai.py`) es un prototipo optativo basado en
**PaddleOCR PP-DocLayout-S**, modelo visual genérico que reconoce regiones
como tablas y gráficos. **No está entrenado para identificar directamente
las mediciones de InBody**. EasyOCR vuelve a leer cada recorte y
`classify_section` aplica reglas sobre títulos conocidos en español/inglés.
No atribuir interpretación semántica a un VLM: **no hay VLM implementado**.

**Estado implementado, sin exagerar:** `ENABLE_AI_SECTION_OCR=1` ejecutaría
un modelo local que requiere `requirements-ai.txt`. El modo está desactivado
por defecto, sin integración validada con ZeroGPU ni benchmark real. Las
pruebas de `tests/test_ai_section_ocr.py` simulan la salida del detector.
`merge_section_ocr` excluye tokens **adicionales** de recortes `history`,
pero **no filtra completamente el historial del extractor global**. No
publicar afirmaciones de exactitud o exclusión total sin evidencia.

**Diseño objetivo:** región identificada → OCR localizado → asignación
de `section` por título → extracción específica por sección → verificar
`metric`, `unit`, `segment`, `value` y coordenadas →
Pydantic → revisión humana → consentimiento → Neon. Marcar explícitamente
las variables desconocidas, las unidades dudosas y los datos faltantes;
jamás completar números según expectativas clínicas o inferir un signo.

**Aceptación:** 22 reportes de referencia privados con datos verificados
manualmente, sin imágenes en GitHub. Medir exact match por valor/unidad/
segmento/timestamp, precisión/recall, errores de historial, latencia,
RAM/VRAM y compatibilidad del Space. Un VLM multimodal es una alternativa
por evaluar si la estrategia visual + OCR no mejora el baseline.
No ejecutar APIs externas con datos personales ni convertir el estado
de un PR en una afirmación de despliegue.

Ver también `harness/04_extraccion_y_normalizacion.md` y
`harness/08_pruebas_y_criterios.md` para reglas y puertas de calidad.


## Continuidad operativa — 2026-11-01 (instrucciones actuales para agentes)

**Leer primero** [harness/10_continuidad_noviembre_2026.md](harness/10_continuidad_noviembre_2026.md). Este documento distingue solicitudes recientes, código observado y validación E2E pendiente. Si contradice secciones históricas que describen EasyOCR como runtime principal, CSV activo o ZeroGPU eliminado, prevalece el estado actual corroborado en código y las decisiones fechadas más recientes. **No reinterpretar deseos como funciones entregadas.**

Al continuar el trabajo: inspeccionar rama/PR y Space antes de afirmar que algo funciona; mantener el flujo Gemini + revisión humana + consentimiento separado + auditoría privada; preservar decimales textuales, timestamp del examen, ID y unidades; no extraer el historial impreso. No añadir columnas de frecuencia artificiales a la tabla de mediciones. Respetar la distinción entre persistencia privada, demo y publicación pública.

**Solicitudes abiertas que no deben perderse:** limpieza de UI después de guardar correctamente; duplicado exacto por nombre de archivo vs conflicto de clave (persona normalizada, fecha/hora de examen, medición) con confirmación explícita antes de sobrescribir; un único popup de errores por operación; selector de modelos Gemini gratuitos/elegibles sin suponer gratuidad permanente; dashboard de estilo InBody con ángulo de fase, comparativas y tendencia de InBody Score; no volver a introducir paneles/componentes retirados sin revisar el diseño vigente. Todo sujeto a pruebas, autorización, aislamiento por usuario y controles de acceso. Documentar resultado de cada entrega y pruebas antes de marcarla completa.

**Nuevo requisito mobile-first (2026-11-01):** interfaz Gradio responsive en celular, tablet y escritorio; tabla de revisión usable como tarjetas/editor por fila en móvil, preview de archivos adaptada, controles táctiles y dashboard Plotly sin recortes. Aplicar criterios de tamaños 360/390/768/1280 px y pruebas de navegador descritos en `harness/10_continuidad_noviembre_2026.md` antes de marcarlo implementado.

**Bugs P0 de revisión (2026-11-01):** el usuario reportó problemas con valores negativos y errores al borrar filas. `validate_review()` actualmente impide cambiar el número de filas y alinea originales por posición; no quitar esa protección sin reemplazarla por identificación estable, exclusión revisada y auditoría íntegra. `_decimal()` admite negativos ASCII en principio; investigar coerción Gradio/Pandas, signo menos Unicode y restricciones SQL antes de declarar causa. Casos de prueba y detalles en `harness/10_continuidad_noviembre_2026.md`, sección 8. Sigue pendiente corrección; este cambio solo documenta.
