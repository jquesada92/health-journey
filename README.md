---
title: Health Journey
emoji: 💪
colorFrom: blue
colorTo: green
sdk: gradio
python_version: "3.12"
app_file: app.py
hf_oauth: true
---

## Fechas InBody: dos formatos de origen y corrección histórica

**Dentro del documento InBody** se imprime la fecha/hora como
`DD.MM.AAAA HH:MM` (p. ej., `04.10.2026 10:04` o
`04.10.2026. 10:04`, con punto final ocasional). El extractor
normaliza este formato a `AAAA-MM-DD HH:MM:SS` y **no** lo interpreta
como mes/día/año ni año/mes/día. Si el año se presenta con dos dígitos
se interpreta explícitamente como 20AA. El reporte puede no incluir
segundos: entonces se representa con `:00`.

**En el nombre del archivo**, inmediatamente después del **primer**
guion bajo, se utiliza otro formato: `AAAAMMDDHHMMSS` (14 dígitos).
Cuando está presente y es válido, **tiene prioridad** para la fecha y
hora del examen y aporta los segundos que no muestra el reporte. La
respuesta original de Gemini se preserva como evidencia y el encabezado
normalizado conserva una traza de la fecha propuesta. Si la marca
del nombre contiene un día/hora imposible, se rechaza el archivo sin
guardar una fecha inventada; si no hay marca válida en esa posición,
se utiliza la fecha del encabezado impreso normalizada. En la UI
esta fecha se muestra antes y después de extraer; el usuario la
verifica junto al documento, sin poder sobrescribir arbitrariamente
una marca válida del nombre.

El inventario de Neon consultado en modo **solo lectura** registró
**17 extracciones**, todas con marca de 14 dígitos en el nombre, y
**17 discrepancias** entre la fecha/hora guardada y la marca del nombre.
En 15 casos coincide el día pero no la hora y en dos cambia también
el día. Se comprobaron las 17 marcas y no se encontraron horas
imposibles ni colisiones de examen entre archivos en la consulta de
diagnóstico. La reparación reproducible está versionada en
`migrations/011_correct_inbody_dates_from_filenames.sql`, que
inserta la fecha anterior y la corregida en una tabla privada
`hj_exam_datetime_repair_history` **antes de actualizar el encabezado
activo**, todo de forma transaccional. No toca mediciones, comentarios
ni respuestas de IA originales. La migración **aún no se ha aplicado
a Neon**: requiere autorización explícita para modificar los
registros históricos; ninguna consulta previa realizó updates.

La reingesta opcional de un archivo existente usa la misma prioridad
de fecha y está protegida en `migrations/010_private_inbody_filename_replace.sql`.
Regresiones sintéticas: `tests/test_inbody_filename_timestamp.py`,
`tests/test_exam_timestamp.py` y
`tests/test_inbody_filename_replacement.py`.
La implementación de UI aún necesita merge y despliegue en HF.


## Volver a subir y reemplazar un InBody ya guardado

La pestaña **Extractor de InBody** permite corregir un examen que ya
había sido registrado: selecciona el mismo nombre de archivo, activa
**Reprocesar y reemplazar el archivo existente en Neon**, extrae de
nuevo con Gemini, comprueba el documento y corrige la tabla,
marca `reviewed` en todas las filas conservadas y pulsa el **único**
botón **Guardar mediciones**.

La opción está **desmarcada por defecto**: sin ella, un archivo
duplicado sigue bloqueado antes de consumir tokens Gemini. Reprocesar
requiere consentimiento firmado para IA y guardar requiere
consentimiento independiente para Neon. Antes de enviar el archivo
a Gemini se comprueba que el nombre pertenece a la identidad privada
autorizada. El reemplazo final exige `DATABASE_URL` privado,
autorización de sesión y coincidencia del ID revisado con la identidad
privada `COACH_PERSON_ID` o el único propietario resuelto por Neon.

**Operación transaccional:** una nueva función SQL privada,
`migrations/010_private_inbody_filename_replace.sql`, bloquea
competidores, verifica nombre y propietario, guarda una copia
confidencial del antiguo header, JSON original y todas las mediciones
en `hj_replaced_audit_backups`, elimina los registros activos
`hj_measurement_audits` y `hj_extraction_audits` de ese archivo
y llama al mismo validador del guardado original para insertar la
nueva versión. Si cualquier paso falla, la transacción se revierte;
no se eliminan datos existentes. El nombre se compara sin
distinción de mayúsculas/minúsculas; no se modifica información de
otros archivos, otros usuarios ni de las tablas del historial
FitNotes. Las copias de recuperación solo pueden consultarse por
el dueño administrativo de Neon.

**Importante:** la función SQL se dejó como migración versionada,
NO se ejecutó en Neon durante el desarrollo y NO se borró ningún
registro existente. Aplicar la migración 010 en el entorno autorizado
antes de habilitar el reemplazo en Hugging Face. El rol
`health_journey_demo_writer` carece expresamente de permiso de
ejecutar el reemplazo. Las pruebas sintéticas cubren consentimiento,
autorización, rollback como contrato, aislamiento y que el
guardado normal sigue intacto: `tests/test_inbody_filename_replacement.py`.


## Compatibilidad de arranque y normalización multilingüe (2026-11-03)

El Space de Hugging Face indica por defecto Python 3.10 si su
README no especifica `python_version`; ahora se declara
`python_version: "3.12"` en el YAML para alinear el runtime
con el Python 3.12 usado en CI. La advertencia de `pip` al
instalar como root corresponde a la imagen administrada y no es
un error fatal del producto. El aviso Gradio
`row_limits parameter is not yet implemented` se evita al
eliminar el parámetro no funcional del `gr.Dataframe`: la
validación de filas conservadas sigue haciéndose en el callback
`save_audit`. El rastro `BaseEventLoop.__del__ / Invalid file
descriptor: -1` proviene de la limpieza del event loop;
el log mostrado contiene `Running on local URL: 0.0.0.0:7860`,
no un fallo fatal de carga de la app. Un cambio de versión
**no garantiza eliminar** esa excepción; verificar nuevamente
los logs del Space después del deploy.

La normalización visual de InBody acepta en el mismo concepto
`Body Fat Percentage`, `Percent Body Fat`,
`Percentage of Body Fat`, así como traducciones españolas,
acentos, variantes explícitas de unidades y nombres de secciones.
La consulta agregada al catálogo revisado de Neon identificó
13 + 2 + 2 registros con las tres etiquetas inglesas de grasa,
mientras los originales se mantienen inmutables. Solo si el
origen especifica `lb/lbs`, la gráfica puede representar peso
en kg usando `0.45359237`; el valor original y su unidad no se
modifican en Neon ni en la auditoría. No se adivina el porcentaje
de grasa a partir de un número sin unidad ni se mezclan resultados
segmentales con medidas globales. Pruebas:
`tests/test_inbody_multilingual_trends.py`,
`tests/test_coach_first_last_trends.py`.


## Corrección de visualización del Coach (2026-11-03)

Las cuatro mini-gráficas del asistente se alinean **a la izquierda
del chat** mediante una cuadrícula CSS de dos columnas: ancho compacto
de 260–320 px para tendencias y espacio restante para el chat completo.
Solo se apilan en pantallas de 900 px o menos, con desplazamiento
vertical dentro del panel de tendencias. El encabezado, privacidad,
historial de burbujas y composer deben permanecer juntos en la
columna derecha; no se modifica la secuencia de mensajes.

Se conservan **exactamente la primera fecha histórica y las diez
más recientes**, sin duplicados (menos puntos si hay menos pruebas).
Para que la primera sea visualmente reconocible, cada minigráfica
presenta los exámenes como posiciones ordinales de igual anchura;
el primer punto se distingue con rombo y color cálido, y las fechas
inicial y final se etiquetan explícitamente en el eje horizontal.
Esto NO es una escala de tiempo proporcional a días. Si una variable
no existe en el primer examen, su posición se mantiene como ausente
(`None`) y se muestra «1.ª prueba: sin esta medida», nunca se crea
un valor ficticio. El texto del panel muestra la fecha inicial y final.

No cambian los permisos privados de Neon ni se consume Gemini para
actualizar tendencias. Pruebas sintéticas y de estructura AST:
`tests/test_coach_first_last_trends.py`. Validación visual de HF
pendiente de despliegue.


## Asistente fitness: minigráficas de la primera y las diez últimas pruebas InBody

El módulo Chat presenta un panel compacto **a la izquierda** del diálogo con
cuatro líneas: peso, masa musculoesquelética, porcentaje de grasa corporal y
puntaje InBody. **Solo se muestran la fecha del primer examen registrado y
las diez fechas de examen más recientes**, en orden cronológico. Si hay diez
fechas o menos no se repite el primer punto. Las fechas intermedias se omiten
intencionalmente y **el filtro de 30/90/180/365 días del chat no afecta
estas gráficas**. La vista auditada de Neon expone solo fecha, por lo que dos
exámenes el mismo día no se pueden distinguir; se representan como un punto
por métrica y fecha. Nunca se inventan medidas ausentes.

La consulta es privada y parametrizada, se comprueba el permiso del
usuario antes de leer Neon y se priorizan auditorías revisadas. Solo si no
hay auditorías se consultan las mediciones confirmadas heredadas. Los
resultados no se envían a Gemini por el hecho de abrir el panel, ni
contienen IDs personales. Los gráficos cargan al abrir Chat y tienen un
botón **Actualizar tendencias**. En móvil aparecen arriba del chat dentro
de un área desplazable de altura limitada. Evidencia sintética:
`tests/test_coach_first_last_trends.py`.


## Entregable académico del Módulo 1 (Fundamentos de la Programación)

El panel **Proyecto** incluye un editor desplegable para documentar la actividad principal de la Sesión 4 de OBS: **ocho apartados en el orden exigido**, con contenidos iniciales basados en el proyecto, un pitch de cinco frases, campos para autor y cuatro capturas reales, vista previa y botón **Generar Word (.docx)**. El Word se crea en la aplicación para descargar, sin llamar a Gemini ni guardar texto de la entrega en la base de datos. El borrador editado vive solo durante la sesión; antes de recargar conviene generar el Word. El HTML aportado contiene requisitos y rúbrica, no la plantilla Word visual de Blackboard. Véanse `docs/entregable-modulo1-obs.md`, `inbody_mvp/module1_deliverable.py` y `tests/test_module1_deliverable.py`.


## Estado vigente de GitHub main (auditoría 2026-11-03)

El árbol `main` `4944fbe5355d66da94290c510e5e0393487f2918` contiene cuatro módulos,
InBody de **cuatro pasos**, un solo botón **Guardar mediciones**,
FitNotes y chat Gemini multiturno con lectura automática privada
InBody/FitNotes y prompts separados. La fuente normativa de cobertura
es [harness/11_cobertura_codigo_main.md](harness/11_cobertura_codigo_main.md),
complementada por [estado 00](harness/00_estado_vigente_y_trazabilidad.md).
El diccionario semántico fue aplicado en Neon; el código lector está
propuesto en PR #84, no debe considerarse desplegado hasta fusionar
GitHub y comprobar Hugging Face. Las referencias antiguas a PRs
abiertos, cinco pasos, OCR/CSV principales son históricas.

## Diccionario semántico InBody y FitNotes en Neon (2026-11-03)

La migración **`migrations/009_ai_semantic_metadata.sql` ya fue aplicada** a
`health_journey` en la rama principal de Neon, sin actualizar datos de
exámenes o series. Define 35 conceptos de InBody con nombre, unidad
orientativa, definición, comparabilidad, interpretación y limitaciones.
Incluye 47 alias normalizados de etiquetas, 24 descripciones de campos y
`COMMENT ON` en las tablas y columnas relevantes. Se reutiliza
`hj_measurement_catalog`; los alias viven en `hj_measurement_aliases`
y el glosario de campos en `hj_ai_field_dictionary`.

El módulo `inbody_mvp/semantic_metadata.py` consulta **solo**
estas definiciones después de la autorización de lectura privada en
`load_coach_context`. Adjunta al JSON enviado a Gemini
`data.semantic_metadata` con las definiciones que correspondan a los
nombres efectivamente leídos (máximo 18 conceptos) y descripciones de
columnas, indicando `available` y `truncated`. Los identificadores,
los comentarios privados y los documentos originales nunca pasan por
este catálogo. Las unidades del catálogo no sustituyen las unidades
que constan en cada fila, y el modelo no debe interpretar estas
definiciones como diagnóstico ni como órdenes privilegiadas.

Las tablas de metadatos tienen lectura autorizada para
`health_journey_app` y `health_journey_runtime`, no para
`health_journey_demo_writer` ni para `PUBLIC`.
Si falta el catálogo en otro entorno, el chat continúa sin
definiciones semánticas, explicitando `available=false`. Para
habilitarlo allí debe aplicarse primero la migración 009.
Los cambios de app requieren fusionar el PR y desplegar Hugging Face
antes de poder verificarse con datos reales.

## Flujo InBody simplificado: una sola confirmación y guardado (2026-11-03)

**Vigente en esta propuesta:** Cargar → Extraer → Revisar → Guardar.
Revisar y Validar ya no son dos pasos. La comparación con el visor original
y las correcciones de `value`, unidad, descripción y comentario se hacen
en la misma tabla. La marca `was_corrected` se sincroniza con el
`original_value` inmutable; el usuario marca `reviewed` al verificar
cada fila. Cuando todas las filas conservadas están revisadas, la barra
avanza visualmente a **Guardar**, sin otro botón ni llamado a Gemini.

Solo existe **Guardar mediciones**: al pulsarlo, el servidor primero
reconcilia cualquier eliminación nativa pendiente y valida todas las
filas y datos generales con `save_audit`; luego escribe en la base de
datos **una sola vez** si el permiso de almacenamiento sigue vigente.
No existe el paso ni botón **Guardar cambios**. Errores de validación
o duplicados se comunican mediante un solo aviso, sin limpiar la tabla.
Tras guardado exitoso, se limpia el examen y el flujo vuelve a Cargar.
El consentimiento de almacenamiento sigue separado del de extracción.

Pruebas: `tests/test_inbody_one_click_review.py`,
`tests/test_inbody_flow.py`, `tests/test_inbody_guided_layout.py`,
`tests/test_inbody_row_actions.py`. El comportamiento en Hugging Face
requiere validación manual después del despliegue.


## Estado consolidado y trazabilidad · 2026-11-03

El estado vigente de capacidades, criterios y documentación se encuentra en
[harness/00_estado_vigente_y_trazabilidad.md](harness/00_estado_vigente_y_trazabilidad.md)
y [docs/indice_actual.md](docs/indice_actual.md). Esta rama conserva los
cambios ya fusionados de los PR #71, #72, #74 y #75, e integra:
la auditoría documental de #73, la edición en tabla de `value` con
`was_corrected` calculado y botón **Guardar cambios** de #76, y la
comprobación privada de nombre de archivo al seleccionarlo para bloquear
extracciones Gemini de duplicados confirmados. La extracción sigue siendo
opcional si no puede comprobarse Neon, mostrando una advertencia. La
confirmación de revisión no escribe en Neon; el guardado de mediciones
sigue exigiendo permiso y comprobación de duplicados.

Ver también [docs/inbody-row-review-actions.md](docs/inbody-row-review-actions.md)
y [docs/inbody-upload-preflight.md](docs/inbody-upload-preflight.md).
El CI no sustituye pruebas reales en el Space ni demuestra migraciones aplicadas.


## Arquitectura de prompts y chat conversacional · noviembre 2026

Los dos módulos Gemini utilizan archivos de instrucciones separados,
versionados y desplegados junto con el código: `inbody_mvp/prompts/inbody_extraction.md`
(extracción estricta de resultados InBody) y
`inbody_mvp/prompts/fitness_coach.md` (asistente basado en literatura
sobre entrenamiento, hipertrofia, fuerza, resistencia, composición
corporal y recuperación). `inbody_mvp/prompt_loader.py` solo permite
leer los prompts declarados. No se guardan claves en estos archivos.

El chat fitness conserva los mensajes en orden dentro de la sesión:
muestra inmediatamente tu burbuja a la derecha y un aviso «Escribiendo…»
mientras espera a Gemini. Enter y Enviar utilizan la misma secuencia
de eventos para evitar duplicados. Gemini recibe una conversación real
con roles `user/model` (historial reciente) y el prompt científico como
`system_instruction`. La historia que ve el usuario se conserva de
manera independiente del contexto abreviado enviado a Gemini.
Si falla una respuesta, la pregunta no desaparece y el error se muestra
dentro del chat, permitiendo formular otra pregunta sin reiniciar.
No se guardan mensajes en Neon. La bibliografía no se busca
automáticamente: el modelo tiene instrucciones expresas de no inventar
fuentes o DOI.



## Health Journey · motivación y propósito

Health Journey integra **mediciones InBody** y **registros de entrenamiento**
para transformar datos dispersos en tendencias que puedas comprender y usar
para planificar tus objetivos. Tras el login, la pantalla inicial **Proyecto**
explica el propósito, el flujo de datos y la arquitectura. La interfaz usa un
único menú lateral con **exactamente cuatro opciones** en este orden:
**Proyecto**, **Extractor de InBody**, **Captador de logs de entrenamiento**
y **Chat con el asistente fitness**.

El dashboard de composición corporal se conserva dentro del módulo InBody,
en un panel desplegable. Se retiró la entrada independiente de Historial y
el menú horizontal con sus controles de overflow. Esto no borra los datos
históricos de Neon ni interfiere con el análisis del asistente.

La nueva sección de chat, implementada en la rama
`feature/ai-coach-simplified-navigation-20261102`, utiliza **Google Gemini
Flash** para examinar resúmenes privados, no documentos completos, y
recomendar ajustes con base en objetivos y restricciones que el usuario
introduce. **No se ha fusionado ni desplegado** esta rama; no se afirma
disponibilidad en el Space antes de verificarla.

**Plataforma:** Gradio en Hugging Face Spaces, Python, Gemini API,
Neon PostgreSQL, SQLAlchemy/psycopg, Pydantic, Pandas, PyMuPDF, Pillow
y Plotly. Consulta `docs/ai-coach.md` para el contrato de privacidad,
los límites de interpretación y las pruebas.

## Consentimiento y tratamiento de datos antes de iniciar sesión

Antes de mostrar el login nativo de Gradio, un middleware del servidor
redirige al visitante a `/privacy`, una pantalla sin acceso a datos privados
que explica las categorías de datos personales y de salud, los fines
(ingesta, revisión, historial y tendencias), los destinatarios externos,
el tratamiento en el servidor, el tiempo de conservación y cómo solicitar
la eliminación de registros. **No se afirma que el sistema tenga un flujo
automático de eliminación si todavía no existe**.

El formulario contiene **tres consentimientos independientes, opcionales y
desmarcados**: enviar documentos InBody a Google Gemini para extraerlos,
almacenar mediciones y entrenamientos en una base de datos y enviar
**resúmenes privados** al chat fitness en Gemini. Un checkbox adicional
obligatorio solo confirma que se leyó el aviso; no autoriza otros usos. Se
puede iniciar sesión sin autorizar ninguna operación.

El servidor recibe las opciones **antes del login** y crea una sesión
aleatoria de duración limitada, identificada por una cookie de sesión
firmada, `HttpOnly` y `SameSite=Lax` (además de `Secure` en el Space
HTTPS). El identificador y las opciones residen únicamente en memoria del
proceso; no se guardan contraseñas ni información de salud en la cookie.
Al cerrar sesión la cookie y la sesión se revocan; al reiniciar el
servidor también quedan invalidadas. No se comparte consentimiento entre
navegadores o usuarios.

Gradio conserva la autenticación original mediante
`authenticate_master_demo`. Al iniciar sesión, los checkboxes de la
aplicación restauran **las opciones declaradas antes del login**. Pueden
modificarse durante la sesión; sus eventos actualizan el registro seguro del
servidor. Los callbacks de extracción Gemini y los de guardado InBody y
FitNotes requieren tanto el consentimiento actual de la interfaz como el
permiso guardado en el servidor, evitando habilitarlos con parámetros
forjados. Sin cookie válida no se puede acceder al login ni a las rutas
de procesamiento de Gradio.

Esta pantalla es un aviso de privacidad práctico, **no una declaración de
cumplimiento legal completo**. Antes de producción con múltiples usuarios,
revisar los avisos y procedimientos de derechos, conservación,
transferencias internacionales y seguridad conforme a la normativa aplicable.

## Encabezado único y editable para exámenes InBody

Después de extraer un reporte, InBody muestra **fecha/hora del examen,
ID de persona, edad y nombre del archivo** en un bloque compacto encima
de la tabla. Los tres primeros campos se pueden corregir **una sola vez**
en lugar de repetir los cambios sobre todas las filas. El nombre del
archivo original permanece de solo lectura como evidencia de origen.

Se requiere **una sola explicación** cuando se modifica un valor del
encabezado. El servidor valida el formato de fecha/hora, edad e ID y aplica
el encabezado revisado a todas las mediciones antes de guardar. Los cambios
en las mediciones siguen requiriendo comentarios de corrección por fila.
El botón **Guardar cambios** confirma de una sola vez todas las filas
conservadas: la interfaz marca `reviewed` automáticamente tras validar,
sin obligar a activar cada casilla manualmente.

La tabla de revisión muestra únicamente los campos correspondientes a
cada medición: sección, nombre, valor, unidad, valor original, indicador
de corrección, comentario y revisión. Se conserva internamente el formato
completo para compatibilidad con otras llamadas y no se modifica la
estructura de la base de datos. La respuesta original de la IA se preserva
como auditoría. El campo `was_corrected` sigue referido únicamente a
cambios de mediciones, para cumplir las validaciones existentes en SQL;
los cambios de encabezado se conservan como comentarios de auditoría.

La carga de otro archivo reinicia la revisión previa. Tras **guardar
correctamente**, la vista previa, el encabezado, la tabla, los mensajes
temporales y el archivo cargado se limpian automáticamente; el progreso
vuelve al paso **Cargar** y se conserva el consentimiento de sesión.
No existe un botón adicional para limpiar todo el examen.
Las pruebas de regresión en `tests/test_inbody_header.py` verifican
campos únicos, IDs con ceros iniciales, negativos, decimales, validación y
preservación de la evidencia.

## Navegación vertical y extracción IA integrada

El menú principal de Gradio incluye solo **Proyecto**, **Extractor de InBody**,
**Captador de logs de entrenamiento** y **Chat con el asistente fitness**,
en ese orden. **Proyecto** es la pantalla inicial. La selección cambia la
visibilidad de cuatro `gr.Column` ya montadas y conserva el estado de la
sesión. No existen `gr.Tabs` horizontales, ni pestaña separada de Historial
ni su menú de tres puntos.

Las tendencias y gráficas Plotly siguen disponibles en el acordeón
**Progreso histórico de InBody** dentro del extractor. La importación
FitNotes permanece en el módulo de entrenamiento. Los callbacks siguen
validando consentimiento y acceso privado del lado servidor.


## Flujo de captura InBody — cinco pasos

El módulo **Extractor de InBody** muestra una barra de navegación fija
**1. Cargar → 2. Extraer → 3. Revisar → 4. Validar → 5. Guardar**,
en la parte superior de la ventana, mientras el usuario se desplaza por
el formulario. La barra usa `position: fixed` y pertenece al nivel
principal de Gradio (fuera del contenedor que hace scroll).
Se activa solo al seleccionar InBody y se oculta al ir a Proyecto,
Captador de logs o Chat. El panel InBody reserva espacio vertical debajo
de la barra para no tapar el título, las instrucciones ni los formularios.
En móvil se ajustan las dimensiones y la barra conserva las cinco etapas.
El encabezado global duplicado permanece eliminado y los permisos
continúan en el menú lateral. La selección de modelo Gemini y el estado
de avance por acciones reales se mantienen sin cambios.

El indicador avanza con eventos reales: **cargar** el archivo desplaza la
pantalla al selector Gemini; **extraer correctamente** lleva a la tabla;
**Guardar cambios** comprueba los valores editados, marca como
`reviewed` todas las filas conservadas y lleva a Validar sin un permiso
adicional de IA; **validar correctamente** lleva
a Guardar; **guardar correctamente** muestra una notificación, limpia
el formulario y vuelve automáticamente al inicio de Cargar con el paso 1
activo. Los cinco desplazamientos respetan la barra fija y las preferencias
de movimiento reducido del navegador.

**No se navega automáticamente ante error**, valores no revisados,
extractor sin resultado o guardado rechazado. Las ediciones de la tabla
no desplazan al usuario: pueden ser numerosas y deben terminarse antes
de pulsar Guardar cambios. Las correcciones después de validar
invalidan la validación anterior. Ni el progreso ni el reinicio otorgan
permisos nuevos de Gemini o Neon ni alteran los consentimientos.

- **Cargar** PDF/imagen: mostrar estado de nombre procesado y vista previa
  del documento, sin enviarlo a Gemini.
- **Extraer**: elegir un modelo disponible, aceptar el consentimiento de IA
  compartido en la sesión y solicitar la extracción manualmente.
- **Revisar**: la tabla editable de mediciones ocupa el ancho completo; el
  PDF/imagen original se consulta en un panel desplegable que evita una vista
  de dos columnas demasiado estrecha en celulares.
- **Validar**: instrucciones claras de columnas editables, comentario de
  corrección y confirmación conjunta con Guardar cambios; el resultado de validación aparece
  al lado de su botón, separado del resultado de extracción.
- **Guardar**: conservar consentimiento de base de datos compartido, ocultar
  la confirmación de sobrescritura tras una sección avanzada, verificar datos
  y mostrar una confirmación emergente. Tras un guardado exitoso, limpiar
  automáticamente el documento, la revisión, los estados y la confirmación
  en línea; retornar al paso 1 sin modificar los permisos de sesión.

Se conserva la verificación de consentimiento en servidor y la validación
previa a cualquier escritura. Los mensajes de pantalla dicen
**«base de datos»** sin nombres de proveedores de almacenamiento.

### Verificación de consentimiento sin advertencias redundantes (2026-11-03)

Al solicitar extracción, el servidor consulta el consentimiento firmado de
IA. El estado local de Gradio no puede invalidar una autorización vigente si
la carga de la página aún no terminó. Si el consentimiento **no** existe, la
extracción continúa bloqueada antes de contactar Gemini. **Guardar cambios**
únicamente confirma los datos de la tabla y no envía nada a la IA ni escribe
en la base de datos; el guardado posterior requiere permiso independiente.

## Consentimiento de sesión para IA y almacenamiento (noviembre de 2026)

La interfaz presenta dos decisiones **independientes**, ambas desmarcadas al entrar:

1. **Procesamiento por IA:** permite enviar las páginas de un reporte InBody
   al proveedor externo Google Gemini **solamente al pulsar Extraer**.
   Cargar un PDF o una imagen sí envía el archivo al servidor del Space para
   la vista previa, aunque no se comparta con Gemini sin consentimiento.
   Importar un CSV de entrenamiento **no lo envía a la IA**.
2. **Almacenamiento en base de datos:** permite guardar medidas InBody
   revisadas y sus datos de auditoría, o series importadas de FitNotes.
   Se guardan identificadores, fechas, métricas y detalles pertinentes.
   El permiso no implica publicar datos ni enviar documentos a Gemini.

Ambas casillas están situadas **fuera de las pestañas** para que sus valores
permanezcan durante la sesión al alternar entre InBody y Training Hub y al
cargar varios archivos. No se restablecen tras subir, guardar o limpiar un
archivo. El usuario puede desmarcarlas en cualquier momento y los siguientes
eventos deben respetar inmediatamente el nuevo valor. En una sesión nueva,
los permisos vuelven a estar desactivados. No se persiste el consentimiento
como preferencia permanente ni se presume que los datos ya guardados deban
borrarse por retirar el permiso. Los registros almacenados permanecen en la
base de datos hasta un proceso explícito de eliminación.

**Controles de backend que se conservan:** `extract_gemini` valida el permiso
de IA, `save_audit` exige permiso de almacenamiento antes de escribir y
`save_training_import` hace lo mismo. Los consentimientos compartidos se
reciben mediante valores de componentes Gradio de la sesión y nunca se
sustituyen por autorizaciones automáticas o marcadas de fábrica.

## Asistente fitness: contexto automático InBody + FitNotes (2026-11-03)

El chat fitness ya no muestra ni exige un campo para introducir el ID
del reporte InBody. Con sesión privada autorizada y consentimiento
específico del chat, **cada pregunta** consulta Neon de forma automática:
primero `hj_audit_reviewed_private` (mediciones revisadas), o el historial
confirmado heredado cuando no existe auditoría; en paralelo consulta
`hj_training_sets` mediante la clave del usuario autenticado.

Se envía a Gemini un **JSON sin identificadores personales** que incluye:
tendencias de InBody por variable y unidades, observaciones recientes
con sus fechas, resúmenes de ejercicios FitNotes y series reales con
peso, repeticiones, fecha y duración. Las observaciones se limitan a la
ventana elegida (30/90/180/365 días), con límites explícitos de tamaño
y `truncated` para no presentar una muestra como historial completo.
Nunca se envían nombres de archivos, texto OCR, IDs, notas de series
ni comentarios de auditoría. El prompt vive en su propio archivo:
`inbody_mvp/prompts/fitness_coach.md`.

La identidad InBody se determina **solo desde servidor**: Secret privado
`COACH_PERSON_ID` (o alias privado ya configurado de Dashboard) si
existe, y si no, detección de un único identificador en la base privada.
Con más de una identidad se bloquea la consulta hasta configurar ese
Secret; no se devuelven registros de otras personas por defecto. El
identificador real nunca se guarda en Git. El rol privado sigue siendo
obligatorio y el consentimiento del chat sigue siendo independiente
del de extracción InBody. La tabla FitNotes conserva el filtro
`owner_key` de la sesión. **No se han verificado consultas reales contra
Neon ni respuestas reales de Gemini como parte de esta implementación.**

Regresiones sintéticas: `tests/test_coach_auto_data.py`,
`tests/test_ai_coach.py` y `tests/test_coach_conversation.py`.

## Inicio de sesión propio `obs-master-demo`

La aplicación puede exigir un login general de Gradio, sin crear una
cuenta adicional de Hugging Face. La cuenta de aplicación
`obs-master-demo` se almacena en **Neon**, en la tabla privada
`hj_app_accounts`, con hash PBKDF2-SHA256, contraseña de alta entropía
y bloqueo de 15 minutos tras cinco intentos erróneos.
La migración `migrations/006_app_master_demo_account.sql` crea
únicamente la tabla; el registro se aprovisiona de forma privada,
**nunca en el repositorio**.

Para activarlo en Hugging Face:

1. Aplicar la migración 006 en Neon.
2. Aprovisionar la cuenta `obs-master-demo` con hash seguro.
3. Añadir la Variable pública `ENABLE_APP_PASSWORD_LOGIN=1` en
   Settings → Variables and secrets. Mantener `DATABASE_URL` como Secret,
   apuntando a un rol privado con permiso sobre `hj_app_accounts`.
4. Reiniciar el Space. Gradio muestra la pantalla de inicio de sesión
   antes de cualquier pestaña; el usuario accede con
   `obs-master-demo` y la contraseña inicial entregada por canal privado.
5. La rotación de contraseña queda como operación administrativa fuera de la interfaz principal; el login de Gradio permanece activo y su verificación continúa en Neon.

   archivos, capturas o logs.

Con el login habilitado, **todos los módulos** quedan detrás de la
pantalla de autenticación: carga, extracción Gemini, revisión,
consentimientos, guardado, Dashboard, historial y diagnóstico.
Los módulos siguen sujetos a sus dependencias normales:
`GEMINI_API_KEY`, `DEMO_DATABASE_URL`, `ENABLE_ANONYMOUS_DEMO`,
`PUBLIC_DATABASE_URL` y vistas SQL. El login no crea datos que no
existan ni autoriza la publicación de exámenes privados.

La lectura de Neon acepta el usuario validado por el middleware de
Gradio mediante `gr.Request.username`. No se acepta un username
enviado por textbox, query string ni un header inventado por el
cliente. Las cuentas OAuth de Hugging Face siguen conservando su
comprobación de `HF_ALLOWED_USERS` cuando el modo de password está
desactivado. Activar el modo login hace que el Space requiera una
sesión para toda la UI; no habilita acceso anónimo al Dashboard.

La protección integrada de Gradio es adecuada para una demostración
controlada, pero **no sustituye** MFA, mitigación de abuso en ingress
y controles de acceso a nivel de fila en un producto multiusuario.
En un Space público, no subir reportes identificables sin tener
un entorno y una política de privacidad apropiados.



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



## Configuración de Hugging Face Spaces

Las cinco **Variables** y los cuatro **Secrets** utilizados por Health Journey
están explicados en la [guía de Variables y Secrets](docs/hugging-face-variables-y-secrets.md).
Incluye propósito, formatos, dependencias, roles SQL, consentimiento,
privacidad y diagnóstico de errores, sin publicar valores confidenciales.

**Resumen:** `ENABLE_PERSISTENCE` habilita el camino privado heredado;
`HF_ALLOWED_USERS` restringe usuarios OAuth; `ENABLE_PUBLIC_DASHBOARD`
habilita lecturas desde vistas públicas; `ENABLE_ANONYMOUS_DEMO` habilita
tanto el demo como las auditorías Gemini consentidas mediante el rol
restringido de `DEMO_DATABASE_URL`. `GEMINI_MODEL` selecciona el
modelo principal, mientras que `GEMINI_API_KEY` permanece en Secrets.

Los cuatro Secrets son `DATABASE_URL` (privado),
`PUBLIC_DATABASE_URL` (solo lectura pública), `DEMO_DATABASE_URL`
(escritura limitada) y `GEMINI_API_KEY` (API de Google).
**No guardar credenciales reales en GitHub.**



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



## Infraestructura actual: Gemini Flash sobre Space ZeroGPU existente (2026-11-01)

El PR #38 ya fue fusionado en `main`. La extracción utiliza Gemini Flash
por API y **no necesita GPU** para procesar los InBody. Sin embargo, el Space
`jaqo/health-journey` sigue asignado a hardware **ZeroGPU** y el usuario
no dispone de CPU Basic en sus opciones de hardware. ZeroGPU exige una
función `@spaces.GPU` conectada a un evento de Gradio **oculto** para superar el
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



# Health Journey

Health Journey es una plataforma modular de salud y bienestar que busca reunir información fragmentada entre aplicaciones que no se comunican, proveedores y documentos heterogéneos. Su visión es construir un historial personal longitudinal y, sobre esa base, un asistente virtual que acompañe hábitos, entrenamientos y objetivos. El primer entregable se concentra en capturar y consolidar evaluaciones InBody; los demás módulos son fases futuras.

Nombre del repositorio: `health-journey`.

## Módulos

| Módulo | Alcance |
| --- | --- |
| **InBody Hub** | Carga, extracción y consolidación de reportes de composición corporal; MVP actual |
| **Training Hub** | Logs y seguimiento del progreso de entrenamiento |
| **Nutrition Hub** | Registros diarios de macronutrientes y alimentación |
| **Medical Hub** | Exámenes e historial médico; ampliación futura |

El asistente personal de Health Journey integrará los datos de estos módulos, comenzando por fitness y ampliándose después a salud. Los módulos representan áreas funcionales; no requieren servicios o repositorios separados.

## Problema que queremos resolver

La información personal de fitness y salud llega desde **aplicaciones que no se hablan entre ellas** y desde fuentes no estructuradas. Un mismo usuario puede tener cinco pruebas InBody en una tienda A y otras seis en una tienda B; aunque son once evaluaciones de la misma persona, los proveedores no comparten el historial. La continuidad de sus tendencias se pierde si debe reunir y comparar cada reporte manualmente.

Incluso los documentos no tienen un formato uniforme:

- PDF con texto seleccionable.
- PDF escaneados o con tablas e información insertadas como imagen.
- Imágenes PNG y JPG del reporte, a veces con distinta calidad, orientación o diseño.
- Más adelante, exportaciones de aplicaciones de entrenamiento o nutrición que no tienen integraciones comunes.

No basta con extraer texto: hay que interpretar cada medición, identificar la fecha, el origen, el equipo y la unidad, mantener la trazabilidad y permitir la revisión de los datos antes de consolidarlos. Tampoco es correcto asumir que todas las mediciones de equipos InBody distintos son directamente comparables. Las tendencias deben advertir diferencias de modelo, definición y unidad.

## Hoja de ruta por fases

### Fase 1 · InBody Hub — consolidación de composición corporal (MVP del reto)

**Objetivo:** unificar exámenes de una misma persona, independientemente del establecimiento, modelo o formato del reporte.

1. Recibir reportes en PDF de texto, PDF con contenido escaneado e imágenes PNG/JPG. **Estado del MVP actual:** Gradio admite PDF, JPG, JPEG y PNG; la extracción tabulada sigue siendo candidata y requiere revisión.
2. Identificar la persona y los metadatos del examen (fecha/hora, establecimiento o fuente, modelo del equipo) y extraer las mediciones disponibles, sin inventar valores.
3. Mostrar la extracción para revisión humana y corrección antes de confirmar el registro.
4. Normalizar nombres y unidades, detectar posibles duplicados, conservar el original o su referencia y consolidar un historial con procedencia.
5. Consultar y comparar la evolución entre evaluaciones, indicando cuándo un cambio de dispositivo o definición limita la interpretación.

**Resultado esperado:** once pruebas procedentes de dos establecimientos se consultan como un único historial cronológico de esa persona, con la fuente de cada examen y sin perder mediciones anteriores.

**Alcance de la versión 0 (semana 2 de OBS):** interfaz Gradio y extracción de texto de imágenes con EasyOCR. Aún no equivale a un flujo completo de extracción estructurada, persistencia o comparación de tendencias.

### Fase 2 · Training Hub + Nutrition Hub — seguimiento de hábitos y progreso

**Objetivo:** reunir los logs de entrenamiento y los registros de macronutrientes para contextualizar la evolución de composición corporal.

- **Entrenamiento:** ejercicios, fecha, series, repeticiones, peso o carga, frecuencia y otros datos disponibles; importación desde archivos de registro o entrada manual.
- **Nutrición:** registros diarios de calorías, proteínas, carbohidratos y grasas, más otros hábitos relevantes cuando el usuario los aporte.
- **Análisis integrado:** relacionar cambios de InBody con la constancia de entrenamiento, volumen, cargas, alimentación y objetivos para identificar patrones y áreas de mejora, sin asumir causalidad automática.

El asistente virtual podrá responder preguntas como «¿Cómo cambió mi composición corporal durante el período en que aumenté la frecuencia de entrenamiento?» y señalar qué información falta para una conclusión más confiable.

### Fase 3 · Medical Hub — integración documental clínica

**Objetivo:** incorporar, de forma voluntaria y protegida, exámenes de laboratorio y documentos clínicos en el historial longitudinal.

- Admitir documentos clínicos en PDF de texto, PDF escaneado o imagen, según el desarrollo futuro.
- Extraer parámetros, fechas, unidades, rangos de referencia y fuente, siempre con posibilidad de revisión.
- Permitir consultas históricas y preparar resúmenes orientados a conversaciones con profesionales.

Los resultados clínicos son datos especialmente sensibles; esta fase exige privacidad, permisos, validación adicional y límites claros. El asistente **no diagnosticará, prescribirá ni reemplazará una evaluación médica profesional**.

### Capacidad transversal · Asistente virtual de Health Journey

El asistente se incorporará de manera incremental a medida que los datos de las fases anteriores sean verificables. Su función será ayudar al usuario a seguir hábitos, entrenamientos y metas; consultar tendencias y ofrecer información contextual basada en fuentes identificables. Debe distinguir hechos de sugerencias, señalar incertidumbre y evitar recomendaciones médicas no justificadas.

## Estrategia de integración de fuentes

| Fuente | Formato de entrada previsto | Tratamiento |
| --- | --- | --- |
| InBody de distintos establecimientos | PDF de texto, PDF escaneado, PNG, JPG | Extracción, validación, normalización y consolidación por persona |
| Aplicaciones y bitácoras de entrenamiento | CSV, exportaciones u otros registros disponibles | Importación y homologación de ejercicios, fechas y cargas |
| Aplicaciones y diarios nutricionales | Exportaciones o registros manuales | Normalización de macronutrientes y calorías por fecha |
| Laboratorios y proveedores clínicos | PDF, imágenes y otros formatos definidos después | Extracción controlada, trazabilidad y protección reforzada |

Ninguna integración externa, API de terceros o soporte de archivos se considera implementado hasta que exista y se pruebe en la aplicación.

## Objetivo de la primera versión

Permitir cargar un reporte, extraer sus mediciones, revisar y corregir la transcripción, confirmar el examen y consultar o exportar los datos consolidados.

La extracción debe ayudar a reducir trabajo manual sin inventar valores. Los campos ilegibles o ambiguos requieren revisión; una carga repetida no debe crear un examen duplicado.

## Flujo principal

1. Seleccionar o registrar una persona.
2. Cargar imágenes o PDF de un reporte InBody.
3. Extraer los datos del examen y las mediciones disponibles.
4. Revisar y corregir la transcripción antes de confirmarla.
5. Consolidar las mediciones en el historial de esa persona.
6. Consultar el historial y exportar la tabla en CSV.

## Formato de datos

La tabla CSV de intercambio y futura vista analítica emplea **una fila por medición**, con siete columnas:

| Columna | Contenido |
| --- | --- |
| `id_persona` | Cédula o identificador **tal como figura en el InBody**, sin asumir identidad verificada |
| `modelo_inbody` | Modelo o identificación del equipo indicada en el documento |
| `timestamp` | Fecha/hora del examen, si ambas aparecen; dejar vacío si no puede confirmarse |
| `variable_medida` | Nombre estandarizado, incorporando segmento/frecuencia cuando proceda |
| `unidad_medida` | Unidad explícita del documento; no se inventa |
| `valor_medida` | Valor numérico, o vacío si no se puede confirmar |
| `edad` | Edad al examen, calculada desde fecha de nacimiento o transcrita si está reportada |

La clasificación distingue masa muscular esquelética, masa libre de grasa, grasa, ángulo de fase y otros parámetros. Las variables nuevas se añaden como **nuevas filas**, no como nuevas columnas. Los metadatos de auditoría, etiqueta original, dimensión, segmento, frecuencia, hash y páginas quedan separados de esta vista. La exportación actual es un **borrador no confirmado**; la persistencia y la consolidación histórica todavía no están implementadas.

## Alcance y límites

El alcance inmediato es la **fase 1**. El prototipo actual ya admite PDF, JPG, JPEG y PNG y ofrece extracción candidata/revisión/CSV. La confirmación persistente, el historial y las tendencias quedan pendientes. Los registros de entrenamiento y macronutrientes corresponden a la fase 2; la integración clínica, a la fase 3. El asistente virtual se incorporará progresivamente, no como capacidad ya disponible.

El diseño contempla CDC hacia Databricks para análisis y un proceso de archivado que reduzca el detalle histórico en la base operativa. Antes de purgar registros, el archivo debe estar verificado y permitir recuperación. Las purgas por archivado deben distinguirse de las eliminaciones reales para no borrar accidentalmente el historial analítico.

## Tecnología y entornos

**Stack del MVP actual:** Python, **Gradio** (interfaz en `app.py`), **Pydantic** (validación), **PyMuPDF** (PDF nativo), **EasyOCR** (imágenes o escaneos), Pandas (tabla y CSV). **Plotly** se usará para las visualizaciones históricas en una fase posterior. No utilizamos Flask ni Dash.

| Entorno | Estado |
| --- | --- |
| Desarrollo local | `python app.py`; archivos temporales y extracción sin base de datos |
| QA en Hugging Face | Gradio + ZeroGPU; datos de prueba sintéticos/anonimizados; publicación por GitHub Actions |
| Producción | Pendiente: acceso privado, PostgreSQL y almacenamiento seguro de originales |

QA no se conecta a producción. No se deben cargar reportes personales reales en un Space público sin controles de acceso y retención.

## Criterios de calidad

- Transcripción revisable y valores respaldados por la fuente.
- Identificadores estables y detección de posibles duplicados.
- Validación de fechas, unidades, relaciones y consistencia de datos.
- Aislamiento de personas y sesiones, con protección de datos de salud.
- Paginación y consultas acotadas para mantener ágil la aplicación.
- Extracción de texto con modelos OCR preentrenados (EasyOCR actual y TrOCR Small de Hugging Face previsto), más reglas deterministas y revisión humana para normalizar las mediciones.
- Uso de IA con contexto mínimo, límites de costo y medición de precisión.

## Contexto del reto OBS · Semana 2

La ficha para Blackboard y el alcance verificable de la versión 0 se documentan en [docs/hito-semana-2.md](docs/hito-semana-2.md). La [especificación](especificacion.md) limita el MVP a tres funcionalidades y define entradas, salidas, restricciones y criterios de aceptación; [AGENTS.md](AGENTS.md) guía a los asistentes de programación.

**Pieza de IA elegida para el reto:** un modelo de Hugging Face ejecutado localmente, [`microsoft/trocr-small-printed`](https://huggingface.co/microsoft/trocr-small-printed), combinado con EasyOCR para detectar regiones de texto. TrOCR reconoce texto impreso de líneas individuales; **no comprende por sí solo un reporte completo ni lo convierte en mediciones estructuradas**. Las reglas de Python/Pydantic identifican y validan las mediciones, que el usuario revisa antes de confirmar. No requiere una API comercial ni tiene cobros por solicitud, pero sí recursos de cómputo y descargas de modelo. En Hugging Face ZeroGPU el alojamiento gratuito está sujeto a elegibilidad, cuotas y disponibilidad. **Estado del reto inicial (histórico):** EasyOCR funcionaba como primera aproximación; TrOCR no está integrado. El MVP posterior añadió PDF y tabulación candidata. No se utilizarán documentos de salud reales en el Space público del reto.

## Estado actual

El punto de entrada **`app.py` utiliza Gradio**. La pestaña **InBody Upload** permite seleccionar PDF, JPG, JPEG y PNG (máximo 15 MB), extraer texto nativo o OCR, revisar mediciones candidatas en una tabla editable y exportar **un CSV borrador vertical de siete columnas**. La clasificación inicial conserva medidas desconocidas y reconoce, cuando el texto lo permite, grasa, masa muscular, segmentos y ángulo de fase/frecuencia.

La pestaña **Dashboard (siguiente fase)** explica el plan para Gradio + Plotly: filtros por fecha, variable, unidades, regiones, grasa vs. músculo y tendencias de ángulo de fase. **Las gráficas históricas, PostgreSQL, la confirmación de exámenes y la detección persistente de duplicados no están implementados.** La pestaña Proyecto muestra este README.

La extracción sigue siendo candidata y requiere revisión humana. La precisión con documentos auténticos y la ejecución efectiva en ZeroGPU deben verificarse por separado. El repositorio contiene pruebas unitarias de extracción y revisión; estas no sustituyen pruebas de interfaz en el Space.

## MVP Gradio: carga y revisión de reportes InBody

El MVP se ejecuta con **Gradio**, sin servidor Dash adicional:

```bash
pip install -r requirements.txt
python app.py
```

Abrir [http://localhost:7860](http://localhost:7860). La publicación en Hugging Face se realiza con `.github/workflows/deploy-huggingface.yml`, que incluye `app.py` y `inbody_mvp/`. Consulta [docs/despliegue-hugging-face.md](docs/despliegue-hugging-face.md).

Para ejecutar las pruebas:
```bash
pip install pytest
python -m pytest -q tests/test_inbody_mvp.py tests/test_review.py
```

## Publicar cambios en Hugging Face Spaces

La publicación del **prototipo Gradio** se hace desde GitHub mediante el workflow [**Sync app to Hugging Face**](.github/workflows/deploy-huggingface.yml). En GitHub, configura el **secret** `HF_TOKEN` (token de Hugging Face con permiso de escritura) y la **variable** `HF_SPACE_ID=jaqo/health-journey` desde **Settings → Secrets and variables → Actions**.

Al hacer push a `main` con cambios en `app.py`, `inbody_mvp/`, `README.md` o `requirements.txt`, el workflow publica **esos archivos y el paquete `inbody_mvp/`** en el Space. También se puede ejecutar desde **Actions → Sync app to Hugging Face → Run workflow**. Para revisar el estado, comprueba primero los logs de GitHub Actions y luego los logs de [Hugging Face Space](https://huggingface.co/spaces/jaqo/health-journey).

**Importante:** el Space usa `app.py` con Gradio y sincroniza `inbody_mvp/`. La versión del dashboard histórico con Plotly y el almacenamiento PostgreSQL aún están pendientes. Reiniciar el Space no sincroniza cambios de GitHub.

**Instrucciones completas:** [docs/despliegue-hugging-face.md](docs/despliegue-hugging-face.md) (configuración, despliegue automático, ejecución manual, CLI, verificación y solución de problemas).

### Extracción de reportes con varias columnas (InBody 580)

El OCR ahora conserva las **coordenadas de cada bloque de texto** (`EasyOCR detail=1`). Para la plantilla **InBody 580**, el módulo `inbody_mvp/layouts.py` usa regiones de la página para recuperar valores de tablas independientes, como composición corporal, grasa segmental, masa magra segmental, agua extracelular y ángulo de fase. Otros modelos mantienen el extractor genérico anterior.

- Las filas son **candidatas** y requieren cotejo visual; no se guardan automáticamente.
- Los porcentajes segmentales de `segmental_fat_reference_percentage` y `segmental_lean_reference_percentage` son relativos a una **referencia del equipo**, no porcentajes de grasa o músculo respecto al peso del segmento.
- No se presupone una frecuencia para el ángulo de fase si no se indica en la fuente.
- Las cifras de referencia, marcas del eje y el gráfico de historial no se convierten automáticamente en medidas de una evaluación actual.
- Valores pequeños o poco nítidos pueden no reconocerse. Si falta una medición, revisar el texto extraído y el original; nunca inventarla.
- **No subir reportes reales ni identificadores personales a un Space público**, al repositorio o a los tests. El código se verificó con fixtures sintéticos; la precisión sobre archivos reales requiere validación separada.

Pruebas: `python -m pytest -q tests/test_inbody_mvp.py tests/test_review.py tests/test_inbody_layouts.py`.

## Idioma del reporte y PostgreSQL en Neon (fase experimental)

Los reportes InBody pueden venir en español o inglés. El extractor detecta de forma conservadora `idioma_reporte` con valores `ES`, `EN` o `UNKNOWN` y permite corregirlo desde Gradio. La etiqueta original se conserva y las variables se normalizan de manera independiente del idioma.

Se creó el proyecto PostgreSQL **health-journey** en Neon, base `health_journey`. Su esquema separa personas, exámenes, mediciones y catálogo; la vista `hj_measurements_long` expone las siete columnas del formato vertical definido. El código de guardado, con validación y detección de duplicados por SHA-256, exige `DATABASE_URL` y `ENABLE_PERSISTENCE=1`. En Hugging Face exige además `HF_ALLOWED_USERS` y autenticación OAuth por operación; **no se debe habilitar para datos reales en un Space público** sin controles de privacidad verificados. La conexión real y la seguridad del despliegue deben comprobarse mediante pruebas de extremo a extremo.

[Guía de Neon, esquema y seguridad](docs/neon-postgres.md) · [DDL versionado](db/schema.sql).


## Harness de reconstrucción y criterios de aceptación

La documentación normativa para reconstruir Health Journey desde cero está en [**harness/README.md**](harness/README.md). Incluye arquitectura, contratos, motor OCR ES/EN, Neon PostgreSQL, CSV portable, dashboard Gradio + Plotly con fuentes Neon/múltiples CSV, seguridad, despliegues, recuperación y **46 criterios verificables** (36 funcionales y 10 de seguridad). Se incluye un [prompt para agentes](harness/PROMPT_AGENTE.md) y un verificador offline `python harness/validar_reconstruccion.py`. Los requisitos pendientes aparecen identificados como objetivos, no como funcionalidades ya desplegadas.

## Dashboard público sin identificadores

La aplicación incluye la vista agregada `hj_public_monthly_summary` y la vista de tendencias individuales **seudonimizadas** `hj_public_person_series`. Esta última expone fechas (sin hora) y valores solo de exámenes autorizados expresamente; utiliza un UUID aleatorio independiente del ID real. El lector público usa únicamente `PUBLIC_DATABASE_URL` de solo lectura. **No se garantiza anonimato irreversible**, pues los patrones de fechas y medidas pueden permitir reidentificación.

**Diseño actualizado: un único Space** puede mantener habilitados el selector PDF/JPG/PNG, OCR, exportación CSV, dashboard público e historial privado de Neon. `ENABLE_PUBLIC_DASHBOARD=1` **ya no deshabilita la carga**. Guardar y consultar historiales privados requiere sesión OAuth autorizada; los datos públicos usan un rol PostgreSQL diferente y solo exámenes con publicación marcada. Si el Space es público, **anonimiza el archivo original antes de subirlo**. La revocación de publicación y la validación E2E todavía están pendientes.

[Diseño, migración y guía de seguridad del dashboard público](docs/dashboard-publico.md).

## Autenticación simplificada

**Extraer un reporte o exportar CSV ya no requiere un login adicional de Hugging Face.** Se eliminó la comprobación manual de sesión de la cabecera. Guardar y consultar historias privadas en Neon mantienen OAuth del servidor; el acceso se encuentra en «Acceso privado a Neon», dentro de la sección de guardado.

Si el Space es público, **anonimiza el archivo antes de subirlo**: elimina cédulas, nombres, fechas de nacimiento y otros identificadores. Procesar un JPG no significa que su contenido deje de estar presente en el servidor.

## Solución al inicio de sesión con pantalla blanca en Hugging Face

Hugging Face OAuth puede fallar al iniciar sesión desde una aplicación Gradio incrustada en un iframe, por cookies de terceros o redirecciones. El flujo del proyecto conserva `hf_oauth: true` y `gradio[oauth]`, pero ahora muestra un enlace **«Iniciar sesión en pestaña nueva»** que utiliza `SPACE_HOST` del propio entorno y la ruta oficial de Gradio `/login/huggingface`.

Después del login, usa **esa misma pestaña independiente** para guardar o consultar Neon; la sesión OAuth pertenece a ese origen. Si la pestaña aparece en blanco, revisa las cookies, extensiones de privacidad o la consola y logs de Hugging Face. Las llamadas privadas conservan la validación de `OAuthProfile.username` contra `HF_ALLOWED_USERS`. El OCR/CSV y el dashboard público no requieren autenticación.

No introducir manualmente `OAUTH_CLIENT_ID` o `OAUTH_CLIENT_SECRET`: Hugging Face los proporciona cuando está activado OAuth con `hf_oauth: true` en el README del Space. No publicar capturas con tokens, URLs de callback que contengan códigos ni secretos.

## Demostración docente sin inicio de sesión

Para que un profesor valide extracción JPG/PDF, corrección de valores, guardado en Neon y dashboard público **sin login**, existe el modo optativo `ENABLE_ANONYMOUS_DEMO=1`. Requiere `DEMO_DATABASE_URL` como Secret independiente del `DATABASE_URL` privado, con un rol SQL restringido a una función segura de inserción. El usuario debe marcar **consentimiento de almacenamiento** y, de manera independiente, **autorización de publicación**, desmarcadas por defecto.

Se almacenan solo medidas numéricas aprobadas, fecha sin hora, modelo sanitizado y alias UUID aleatorio. **No** se guarda la cédula/ID, edad, texto OCR ni el documento original en las tablas demo. La vista pública de los datos autorizados deja de mostrarlos tras 7 días; una limpieza física posterior es necesaria. En modo demo no hay acceso anónimo a consultas o escrituras de tablas privadas. No es anonimización irreversible. [Guía de la demostración sin login](docs/demo-anonima-consentimiento.md).

## Fecha y hora del examen: siempre desde el reporte

La fecha/hora del examen **se extrae automáticamente** del encabezado de su PDF/JPG/PNG mediante texto nativo u OCR (incluidos encabezados españoles «Fecha de medición», «Fecha de examen» y los equivalentes ingleses). Se muestra en una caja **de solo lectura**. El usuario no debe rellenarla ni sustituirla por la fecha actual.

Al exportar CSV o guardar en Neon (incluyendo modo demostración sin login), el servidor utiliza el timestamp del `ExtractionResult`, **no** un campo editable de Gradio. `prepare_confirmed_exam` rechaza una fecha que difiere de la detectada en el reporte. Si faltan fecha u hora, se bloquean guardado y exportación del CSV y se solicita verificar la legibilidad del encabezado/volver a extraer, **sin inventar un valor**. El dashboard público muestra solo fecha (no hora).

## Encabezados InBody con fecha y hora en la siguiente línea

El extractor reconoce directamente el encabezado impreso en distintos modelos, incluidos `Test Date / Time\n04.10.2026. 10:04` y `Fecha / Hora del test\n26.01.2025. 14:20`. También acepta que ambos valores estén en la misma línea, años sin punto final y fechas ISO. Un punto adicional después de `AAAA` forma parte de la puntuación del reporte, **no** de la fecha.

La fecha y la hora deben venir juntas del documento (nunca del reloj del sistema). Si el OCR no las reconoce, se muestra un error y no se permite inventar ni editar el timestamp antes de guardar en Neon. Las nuevas pruebas reproducen ambos encabezados mediante texto e imágenes de prueba sintéticas, sin subir informes personales al repositorio.

## Corrección del OCR de fecha/hora en dos columnas

El problema de los reportes InBody JPG no era solo Regex. EasyOCR puede recuperar la cabecera `Gender / Test Date / Time` o `Género / Fecha / Hora del test` como una misma línea, mientras el texto de `DOB` y el timestamp aparecen mezclados en la línea siguiente. Se añadió `extract_header_exam_timestamp`, que lee **directamente los cuadros OCR por posición** en el encabezado y usa únicamente la columna del examen. Se conservan las reglas de Regex para texto digital y el reconocimiento por plantilla. Se rechazan fechas inválidas, sin hora o fuera de la línea de examen. El parser de siluetas españolas ya no borra un timestamp explícito y correcto al fusionar resultados. Las pruebas usan cuadros de texto sintéticos, no imágenes médicas reales.

## IA para identificar secciones antes del OCR (experimental)

Los reportes InBody no son una lista lineal de cifras: contienen **secciones, columnas,
tablas, porcentajes de referencia y gráficas históricas**. EasyOCR puede
reconocer los caracteres y, aun así, asociar un número a una métrica errónea.
Por eso se está evaluando un **pipeline basado en regiones del documento**:

1. **Visión artificial — `PP-DocLayout-S`:** identifica rectángulos genéricos
   como tablas, textos y gráficos, y devuelve coordenadas y confianza de
   detección. Fue preentrenado para reconocer tipos de bloques visuales; **no
   sabe de forma nativa qué mide un InBody**.
2. **EasyOCR por región:** lee cada recorte y devuelve texto con coordenadas.
3. **Clasificación de secciones:** compara títulos como *Muscle-Fat Analysis*,
   *Segmental Lean Analysis* o *Body Composition History* para asignar el
   significado correspondiente. **Actualmente esta parte usa reglas, no un VLM**.
4. **Reconciliación y validación:** combina candidatos con OCR global,
   aprovecha los parsers de las plantillas y exige revisión antes de CSV/Neon.

**Estado preciso:** `inbody_mvp/section_ai.py` tiene la integración
experimental y `ENABLE_AI_SECTION_OCR` comienza deshabilitado. Sus tests
utilizan detecciones simuladas; aún **no se ha demostrado** mayor exactitud
con imágenes reales, ni compatibilidad del modelo adicional con el
runtime de ZeroGPU. El filtro actual excluye nuevos tokens OCR del recorte
del historial, **pero aún no aísla por completo los resultados del extractor
global**. Por eso no se debe afirmar que toda cifra histórica está excluida.

**Alternativas pendientes:** comparar el baseline (EasyOCR + Regex) contra
layout + OCR y eventualmente contra un Vision-Language Model (VLM) documental.
Un VLM no está integrado actualmente. La decisión requiere ground truth
revisado manualmente y mediciones de exactitud por valor, unidad, sección,
segmento, fecha, falsos positivos, latencia y memoria.

**[Guía completa: cómo la IA detecta secciones, arquitectura, ejemplo,
limitaciones, evaluación y privacidad](docs/ocr-secciones-ia.md).**

## Validación de duplicados y limpieza del formulario (migración 007)

El botón «Guardar mediciones revisadas y auditoría» comprueba en una
**transacción en Neon** y en este orden:

1. **Archivo ya procesado:** coincidencia de nombre sin distinguir
   mayúsculas/espacios exteriores, o contenido SHA-256 idéntico.
   Se muestra «Este archivo ya fue procesado», sin crear otra auditoría.
   En una sesión privada autorizada la carga también consulta
   anticipadamente el nombre mediante
   `hj_audit_filename_processed(text)`.
2. **Mediciones duplicadas:** si el **ID numérico normalizado**, la
   **fecha y hora exactas del examen** y el **nombre de medición**
   coinciden con una auditoría previa, el guardado se detiene y avisa
   cuántos valores ya fueron capturados. Es necesario marcar
   **«Confirmo sobrescribir mediciones anteriores»** y guardar de nuevo.
   Este consentimiento es distinto del de almacenar en Neon.
3. **Guardado nuevo o actualización aprobada:** se inserta la nueva
   auditoría completa; la vista privada
   `hj_audit_reviewed_private` muestra solo la versión más reciente
   para cada persona/fecha exacta/medición. La versión anterior **no se
   elimina**: permanece como evidencia de auditoría. Las mediciones
   no presentes en el nuevo documento se conservan del anterior.
   Si una medición aparece varias veces en el documento nuevo, la vista
   conserva esas filas, no inventa agregados.
4. **Limpieza automática solo al guardar con éxito:** se retiran archivo,
   visor PDF, tabla, respuesta Gemini, consentimientos y confirmación
   de sobrescritura. Se notifica el éxito. Si hay duplicados o un
   error, no se destruye la revisión que el usuario está corrigiendo.

La ruta mantiene `ENABLE_ANONYMOUS_DEMO=1` y el Secret
`DEMO_DATABASE_URL` con el rol restringido
`health_journey_demo_writer`. No concede SELECT directo a ese rol.
La migración 007 incluye el procedimiento transaccional
`hj_submit_reviewed_audit_receipt`, la comprobación de archivo y la
vista de últimas mediciones. Los códigos de error SQLSTATE se registran
**sin** valores personales, SQL bruto, tokens o contraseñas.

La comprobación anticipada de nombres está disponible solo con una
sesión privada autorizada, para no permitir enumeración anónima de
archivos de salud. La validación de duplicados en el guardado siempre
se ejecuta en Neon. **No se elimina ni modifica la cuenta
`obs-master-demo`.**


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


### Interfaz principal simplificada

Se retiraron del inicio los paneles «Seguridad de la cuenta (cambiar contraseña)» y «Diagnóstico ZeroGPU (opcional)». La autenticación `obs-master-demo` sigue operativa, pero la rotación de contraseña se gestiona administrativamente fuera de la UI principal. Se conserva un evento ZeroGPU **invisible y no expuesto como endpoint público** para evitar fallos de arranque del Space en hardware ZeroGPU. La carga, Gemini, Neon y el Dashboard no utilizan GPU.


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
