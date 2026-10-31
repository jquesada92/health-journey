---
title: Health Journey
emoji: 💪
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
hf_oauth: true
---

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
