# Especificación · Health Journey (Fase 1: InBody Hub)

> Documento de la semana 2 del reto de Fundamentos de programación (Python para IA), OBS. Esta especificación se centra en la fase 1; la visión global y la hoja de ruta están en [README.md](README.md).

## 1. Problema y usuario

- **Quién tiene el problema:** personas que entrenan y hacen evaluaciones periódicas de composición corporal en establecimientos diferentes, o que usan aplicaciones independientes para entrenamiento y nutrición.
- **Cómo lo resuelve hoy:** guardan informes aislados, consultan históricos limitados a cada proveedor o transcriben resultados manualmente a hojas de cálculo.
- **Qué le molesta:** las aplicaciones no intercambian datos; los historiales se fragmentan entre establecimientos y los archivos llegan como PDF con texto, PDF escaneado, PNG o JPG. Ejemplo: 5 pruebas en la tienda A y 6 en la tienda B no aparecen como una serie única.
- **Qué parte resuelve la IA:** interpretación de documentos de formatos variables y extracción candidata de mediciones y metadatos. Las reglas deterministas validan tipos, fechas, unidades y duplicados; una persona confirma cualquier lectura ambigua.
- **Qué queda fuera en esta fase:** análisis de entrenamientos/macronutrientes, recomendaciones clínicas y conexión automática a cuentas de terceros.

### Usuario tipo

Persona que visita centros de evaluación distintos y necesita consultar su evolución corporal sin depender del historial aislado de cada proveedor. Para el reto se usarán únicamente documentos ficticios o anonimizados.

## 2. Qué hace el producto

**Máximo tres funcionalidades para el MVP funcional de la fase 1:**

1. **Capturar:** subir reportes InBody en PDF de texto, PDF escaneado, PNG o JPG, con validación de tipo, tamaño y calidad básica.
2. **Extraer y validar:** reconocer metadatos y mediciones presentes, mostrar el resultado en una pantalla editable, marcar lecturas inciertas y confirmar el examen sin inventar valores.
3. **Consolidar y consultar:** mantener las mediciones en un historial por persona y fecha, preservar procedencia/modelo/unidades, advertir comparaciones incompatibles y permitir consultar o exportar el historial.

**Estado real de la versión 0 (14/10/2026, según el código revisado):** solo está disponible una interfaz Gradio que acepta **imágenes** y devuelve **texto OCR** de EasyOCR; todavía no admite PDF, no tabula mediciones ni persiste historiales. La lista anterior define resultados esperados, no funcionalidades desplegadas.

## 3. Entradas y salidas

| El usuario da… | La app devuelve… | Ejemplo |
| --- | --- | --- |
| Imagen de reporte InBody (versión 0) | Texto extraído para revisión; no se guarda | JPG → líneas reconocidas por OCR |
| PDF de texto o PDF escaneado (objetivo fase 1) | Campos candidatos, fuente y alertas de confianza/lectura | PDF → peso, masa muscular, grasa corporal si aparecen |
| Correcciones y confirmación (objetivo) | Examen validado con ID estable y mediciones normalizadas | Reporte tienda A → registro cronológico |
| Solicitud de historial (objetivo) | Pruebas de todos los establecimientos ordenadas por fecha y advertencias | 5 pruebas A + 6 pruebas B → 11 registros de pruebas, si no hay duplicados |

### Modelo conceptual mínimo

- **Persona:** identificador estable y controles de acceso. No usar identificadores personales reales en QA.
- **Examen:** ID único, persona, fecha y hora cuando estén disponibles, zona horaria si se conoce, establecimiento/fuente, modelo del equipo, identificador o huella de archivo para trazabilidad.
- **Medición:** una fila por parámetro, con nombre normalizado, valor, unidad, segmento corporal si corresponde y estado de validación.
- **Archivo de origen:** referencia trazable al original, sin exponer información sensible en registros, prompts o pruebas públicas.

No sustituir datos faltantes por cero. Las medidas obtenidas con modelos distintos pueden diferir; evitar líneas de tendencia que oculten esa discontinuidad.

## 4. La pieza de IA

- **Opción elegida:** un modelo de Hugging Face descargado y ejecutado dentro de la aplicación, [`microsoft/trocr-small-printed`](https://huggingface.co/microsoft/trocr-small-printed), junto con EasyOCR.
- **Por qué:** evita facturación por llamadas a una API y conserva la opción de procesar documentos localmente. TrOCR Small es un modelo neuronal para reconocer texto impreso en imágenes de una sola línea; EasyOCR detecta regiones de texto y puede actuar como OCR alternativo.
- **Estado actual:** `app.py` usa EasyOCR; TrOCR todavía no está integrado ni probado con reportes InBody. El soporte PDF y la estructuración de mediciones siguen pendientes.
- **Cómo se aplicará:** (1) extraer texto nativo de PDF cuando exista o renderizar páginas escaneadas a imagen; (2) detectar líneas/regiones; (3) aplicar TrOCR Small a recortes apropiados y contrastar con EasyOCR cuando aporte valor; (4) asociar etiquetas y valores con reglas de Python, validar mediante Pydantic y exigir revisión de ambigüedades.
- **Limitaciones:** el modelo no entiende por sí solo la estructura completa de tablas InBody; podría leer números o etiquetas de forma incorrecta y requerirá pruebas con variantes de plantilla. No debe inventar mediciones ni inferir valores ausentes.
- **Coste:** cero por peticiones de inferencia al ejecutar los pesos descargados por cuenta propia. El Space ZeroGPU gratuito está sujeto a requisitos de elegibilidad, cuotas de minutos y disponibilidad; si estas se agotan, mostrar aviso y ofrecer reintento posterior o ejecución local, sin migrar automáticamente a servicios facturables.
- **Seguridad:** procesar solo documentos sintéticos o anonimizados en el Space público. No enviar información de salud a APIs externas; validar archivos, limitar tamaño y evitar imprimir datos personales en logs.
- **Reglas para el agente de programación:** documentar identificador exacto del modelo y versión, descargar los pesos de fuente confiable, cachear el modelo, limitar cargas y tiempo de inferencia, no cambiar a un servicio de pago sin autorización y registrar resultados de pruebas antes de declarar soporte para un formato.

## 5. Flujo del usuario

**Flujo previsto de fase 1:**

1. El usuario selecciona una persona o inicia un registro de prueba ficticio.
2. Carga uno o más archivos compatibles y ve una vista previa.
3. Se extraen metadatos y valores candidatos; los campos dudosos se señalan.
4. Revisa/corrige y confirma, o cancela sin guardar.
5. El sistema detecta posibles duplicados y consolida por persona, sin mezclar individuos.
6. El usuario consulta el historial y filtra por fecha, fuente y modelo.

**Flujo disponible hoy:** subir imagen → ejecutar OCR → revisar el texto en Gradio; nada se guarda en una base de datos.

## 6. Restricciones

- Coste cero para el reto; usar opciones gratuitas en QA y datos ficticios o debidamente anonimizados.
- No subir secretos, credenciales ni datos personales al código, README, chat o repositorio. La pieza OCR elegida no necesita clave de API.
- No permitir documentos clínicos reales en un Space público del reto; los datos de salud requieren privacidad, aislamiento por usuario, consentimiento y política de retención antes de una operación real.
- Máximo tres funcionalidades centrales durante el reto.
- Interfaz en español y mensajes comprensibles para usuarios no técnicos.
- No confundir datos faltantes con cero ni comparar como equivalentes parámetros de modelos/dispositivos incompatibles.
- Toda lectura ambigua requiere confirmación humana. Prohibido inventar mediciones.
- El repositorio contempla React/FastAPI/PostgreSQL para fases posteriores; la versión 0 es Gradio y EasyOCR.

## 7. Criterios de aceptación

| Entrada | Resultado esperado |
| --- | --- |
| Imagen válida de ejemplo (versión 0) | Aparece el texto detectado y puede revisarse; no se afirma que haya extracción estructurada |
| Sin archivo (versión 0) | Mensaje claro pidiendo cargar imagen |
| Imagen demasiado grande (versión 0) | Error claro sin procesar el archivo |
| PDF con texto seleccionable (objetivo fase 1) | Se extraen datos presentes y se muestra vista editable |
| PDF escaneado / PNG / JPG de distinto formato (objetivo) | Se identifican candidatos o se marcan ilegibles sin inventar |
| Campo sin unidad / ilegible (objetivo) | Se marca para revisión; no se confirma automáticamente |
| 5 pruebas tienda A + 6 tienda B (objetivo) | Un historial con 11 pruebas únicas ordenadas cronológicamente y con sus respectivas fuentes |
| Reimportación del mismo examen (objetivo) | Se informa posible duplicado y no se inserta silenciosamente |
| Cambio de modelo InBody (objetivo) | Se conserva el modelo por prueba y aparece advertencia de comparabilidad |
| Cuota ZeroGPU agotada, modelo no disponible o error de descarga (objetivo) | Aviso claro y opción de reintento o ejecución local, sin activar servicios de pago |

Los casos de objetivo deben verificarse al implementarse; no están declarados como pruebas superadas.

## 8. Fuera de alcance (por ahora)

- **Fase 2:** consolidar logs de ejercicios (series, repeticiones, cargas y frecuencia) y macronutrientes (proteína, carbohidratos, grasas y calorías) para relacionarlos con composición corporal y hábitos.
- **Fase 3:** integrar resultados de exámenes médicos/clínicos, preservar unidades, rangos y origen, y ofrecer historial consultable con protección reforzada.
- **Asistente virtual transversal:** seguimiento de objetivos, hábitos y entrenamientos basado en datos de las fases previas, con incertidumbre y referencias. No diagnóstico ni sustitución de profesionales.
- Integraciones automáticas con aplicaciones de terceros, sincronizaciones de datos y analítica avanzada.
- CDC hacia Databricks y archivado productivo, que son metas arquitectónicas posteriores.

## 9. Despliegue

- **Ruta elegida:** B — Hugging Face Spaces con Gradio y ZeroGPU para la versión 0.
- **Repositorio:** `jquesada92/health-journey`.
- **Archivo de entrada actual:** `app.py` (Gradio + EasyOCR); `README.md` conserva la cabecera YAML del Space.
- **Enlace público:** verificar desde navegador en modo incógnito antes de publicar en Blackboard; que el repositorio exista no confirma que el Space esté funcionando.
- **Próximos pasos:** documentar pruebas con datos sintéticos, experimentar con TrOCR Small para reconocimiento de líneas, completar el soporte de PDF, revisión humana y tabulación. Medir precisión y tiempos antes de asumir que el modelo mejora a EasyOCR.
