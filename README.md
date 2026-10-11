# Health Journey

Proyecto modular para reunir composición corporal, entrenamiento, nutrición y, en una etapa futura, exámenes médicos en un historial personal que alimente un asistente de fitness y salud.

Nombre del repositorio: `health-journey`.

## Módulos

| Módulo | Alcance |
| --- | --- |
| **InBody Hub** | Carga, extracción y consolidación de reportes de composición corporal; MVP actual |
| **Training Hub** | Logs y seguimiento del progreso de entrenamiento |
| **Nutrition Hub** | Registros diarios de macronutrientes y alimentación |
| **Medical Hub** | Exámenes e historial médico; ampliación futura |

El asistente personal de Health Journey integrará los datos de estos módulos, comenzando por fitness y ampliándose después a salud. Los módulos representan áreas funcionales; no requieren servicios o repositorios separados.

## Visión del proyecto: dos partes

### Parte 1: consolidación de InBody

Cargar reportes InBody, extraer y revisar sus mediciones, tabularlas y consolidarlas en una base de datos. Construir un historial por persona que conserve la fecha, el modelo del equipo y la procedencia de cada dato.

### Parte 2: asistente fitness

Ampliar el historial con dos fuentes adicionales, incorporadas progresivamente:

1. **Logs de entrenamiento:** cargar registros de ejercicios, series, repeticiones y cargas para seguir el progreso.
2. **Macronutrientes diarios:** incorporar registros de proteínas, carbohidratos y grasas, junto con las calorías cuando estén disponibles.

Integrar estos registros con las mediciones InBody para crear un asistente fitness personalizado que ayude a planificar y ajustar entrenamiento y alimentación según objetivos, progreso y recuperación.

### Ampliación futura: perfil de salud integral

Incorporar también exámenes médicos para reunir un perfil de salud longitudinal que sirva como base para un asistente médico personal. Conservar fechas, unidades, rangos de referencia y fuentes de los resultados, con controles de privacidad y acceso. Esta ampliación requerirá definir su alcance clínico y validación; el asistente apoyará el seguimiento y la preparación de consultas sin sustituir la evaluación profesional.

Estas capacidades describen la evolución prevista del proyecto. El MVP actual se limita a la primera parte.

## Problema que quiero resolver

1. **Solo recibimos un PDF.** Al realizar una prueba InBody en una tienda o con un nutricionista, recibimos un reporte aislado, sin datos estructurados que podamos consultar y reutilizar fácilmente.
2. **El historial se fragmenta entre máquinas.** Al realizar exámenes en equipos o establecimientos distintos, se pierde la continuidad del registro y resulta difícil comparar las mediciones de una misma persona a lo largo del tiempo.
3. **El formato cambia según el modelo.** Los reportes pueden presentar diferentes distribuciones, etiquetas y mediciones disponibles, lo que dificulta consolidarlos en una tabla común.

Quiero centralizar estos reportes y transformar sus mediciones en un historial confiable, conservando la relación entre cada dato, la persona, el examen y su fuente. También quiero separar la captura operativa del análisis histórico para que la aplicación siga siendo ágil a medida que crecen los datos.

InBody Hub permitirá cargar los reportes, revisar la extracción y normalizar nombres y unidades para reunirlos en un historial cronológico por persona, conservando el modelo de cada examen. La consolidación no implica que todas las mediciones de equipos distintos sean equivalentes: las comparativas deben identificar cambios de modelo y diferencias de definición o unidad. Las mediciones que un reporte no incluya permanecerán ausentes.

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

La tabla de intercambio usa una fila por medición. Las filas de un mismo examen comparten el ID InBody y sus metadatos.

| Columna | Contenido |
| --- | --- |
| `id_inbody` | Identificador único y estable del examen |
| `id_persona` | Identificador estable de la persona |
| `edad` | Edad en la fecha del examen |
| `fecha` | Fecha local del examen, `YYYY-MM-DD` |
| `timestamp` | Fecha y hora del examen con zona horaria, si se conocen |
| `modelo_inbody` | Modelo del equipo indicado en el reporte |
| `descripcion_medicion` | Nombre normalizado de la medición, incluyendo unidad y segmento cuando corresponda |
| `valor_medicion` | Valor numérico; ausente cuando no se pueda confirmar |

Las unidades se documentan en el diccionario de mediciones. Los datos ausentes no se sustituyen por cero. La fuente y la trazabilidad se conservan aparte de estas ocho columnas.

## Alcance y límites

Esta etapa comprende carga, extracción, validación, consolidación, consulta y exportación de reportes InBody. Los logs de entrenamiento, los registros diarios de macronutrientes y el asistente fitness pertenecen a la segunda parte. Los exámenes médicos y el asistente médico personal corresponden a una ampliación posterior.

El diseño contempla CDC hacia Databricks para análisis y un proceso de archivado que reduzca el detalle histórico en la base operativa. Antes de purgar registros, el archivo debe estar verificado y permitir recuperación. Las purgas por archivado deben distinguirse de las eliminaciones reales para no borrar accidentalmente el historial analítico.

## Tecnología y entornos

Stack: React con TypeScript y Vite; Python con FastAPI y Pydantic; PostgreSQL con SQLAlchemy y Alembic.

| Entorno | Ejecución | Datos |
| --- | --- | --- |
| Desarrollo | Todos los servicios en local mediante Docker Compose | PostgreSQL y archivos locales; pruebas independientes de producción |
| QA | React, FastAPI, OCR y PostgreSQL dentro del mismo Hugging Face Docker Space | Datos temporales, sin almacenamiento durable; base vacía en cada arranque |
| Producción prevista | Frontend en Vercel, backend en Render y PostgreSQL en Neon | Persistencia durable; almacenamiento de originales pendiente de elección |

QA no se conecta a servicios de producción y usa datos ficticios o anonimizados. CDC y archivado de producción permanecen desactivados en ese entorno. Su objetivo es probar el flujo de la app, no conservar historiales reales.

## Criterios de calidad

- Transcripción revisable y valores respaldados por la fuente.
- Identificadores estables y detección de posibles duplicados.
- Validación de fechas, unidades, relaciones y consistencia de datos.
- Aislamiento de personas y sesiones, con protección de datos de salud.
- Paginación y consultas acotadas para mantener ágil la aplicación.
- Extracción determinista y OCR local antes de recurrir a modelos de IA.
- Uso de IA con contexto mínimo, límites de costo y medición de precisión.

## Estado actual

El proyecto cuenta con instrucciones de arquitectura en `AGENTS.md`, un `app.py` con Gradio que renderiza este README y un archivo `requirements.txt` con las dependencias Python.

La vista actual en Gradio muestra documentación; el QA completo con React, FastAPI y PostgreSQL sigue siendo un objetivo posterior.

El flujo InBody, la interfaz React, la base de datos, el contenedor QA, CDC y archivado todavía no están implementados. Los entornos descritos son objetivos de diseño, no despliegues verificados.

### Ejecutar el ejemplo mínimo

```bash
pip install -r requirements.txt
python app.py
```

Abrir http://localhost:7860. Mantener `README.md` junto a `app.py`: se lee en cada solicitud, por lo que los cambios aparecen al recargar la página. Este ejemplo no inicia PostgreSQL ni el flujo de carga de reportes.
