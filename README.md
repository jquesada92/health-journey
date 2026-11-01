---
title: Health Journey
emoji: 💪
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
hf_oauth: true
---

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

El esquema se probó en rama temporal de Neon con **IDs sintéticos**
equivalentes: dos exámenes → un mismo UUID; sin acceso SELECT para
roles públicos o de demostración. La migración 005 de `main` de
Neon permanece pendiente de aprobación, así que el guardado y la
consulta de esta vista no están activos aún en producción.



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
`ENABLE_ANONYMOUS_AUDIT=1` (Variable HF). La migración
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
