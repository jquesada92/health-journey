---
title: Health Journey
emoji: 💪
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
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

1. Recibir reportes en PDF de texto, PDF con contenido escaneado e imágenes PNG/JPG. **Estado actual:** la versión 0 admite imágenes para OCR; los PDF están pendientes.
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

El alcance inmediato es la **fase 1**. La versión 0 del reto incluye únicamente la interfaz y OCR de imágenes, con datos de prueba o anonimizados. La carga de PDF, extracción estructurada, validación, historial y tendencias son objetivos siguientes de esta fase. Los registros de entrenamiento y macronutrientes corresponden a la fase 2; la integración clínica, a la fase 3. El asistente virtual se incorporará progresivamente, no como capacidad ya disponible.

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
- Extracción de texto con modelos OCR preentrenados (EasyOCR actual y TrOCR Small de Hugging Face previsto), más reglas deterministas y revisión humana para normalizar las mediciones.
- Uso de IA con contexto mínimo, límites de costo y medición de precisión.

## Contexto del reto OBS · Semana 2

La ficha para Blackboard y el alcance verificable de la versión 0 se documentan en [docs/hito-semana-2.md](docs/hito-semana-2.md). La [especificación](especificacion.md) limita el MVP a tres funcionalidades y define entradas, salidas, restricciones y criterios de aceptación; [AGENTS.md](AGENTS.md) guía a los asistentes de programación.

**Pieza de IA elegida para el reto:** un modelo de Hugging Face ejecutado localmente, [`microsoft/trocr-small-printed`](https://huggingface.co/microsoft/trocr-small-printed), combinado con EasyOCR para detectar regiones de texto. TrOCR reconoce texto impreso de líneas individuales; **no comprende por sí solo un reporte completo ni lo convierte en mediciones estructuradas**. Las reglas de Python/Pydantic identifican y validan las mediciones, que el usuario revisa antes de confirmar. No requiere una API comercial ni tiene cobros por solicitud, pero sí recursos de cómputo y descargas de modelo. En Hugging Face ZeroGPU el alojamiento gratuito está sujeto a elegibilidad, cuotas y disponibilidad. **Estado actual:** EasyOCR funciona como primera aproximación; TrOCR, PDF y tabulación todavía no están integrados. No se utilizarán documentos de salud reales en el Space público del reto.

## Estado actual

El proyecto cuenta con instrucciones de arquitectura en `AGENTS.md`, un `app.py` con Gradio que renderiza este README y un archivo `requirements.txt` con las dependencias Python.

La vista actual en Gradio muestra documentación y permite extraer texto de imágenes con EasyOCR mediante `@spaces.GPU` en ZeroGPU. El texto requiere revisión; la precisión con reportes InBody y la ejecución GPU aún no están verificadas. PDF y tabulación estructurada siguen pendientes. En local, se usa CPU cuando CUDA no está disponible; los modelos OCR se descargan en el primer arranque.

La interfaz QA completa con React, FastAPI y PostgreSQL sigue siendo un objetivo posterior.

El flujo InBody, la interfaz React, la base de datos, el contenedor QA, CDC y archivado todavía no están implementados. Los entornos descritos son objetivos de diseño, no despliegues verificados.

### Ejecutar el ejemplo mínimo

```bash
pip install -r requirements.txt
python app.py
```

Abrir http://localhost:7860. Mantener `README.md` junto a `app.py`: se lee en cada solicitud, por lo que los cambios aparecen al recargar la página. Este ejemplo no inicia PostgreSQL ni el flujo de carga de reportes.
