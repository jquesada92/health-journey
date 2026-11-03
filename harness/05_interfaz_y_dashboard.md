# 05 — Interfaz actual, navegación y dashboard

## Variantes de medidas y unidades de InBody (2026-11-03)

El panel de chat con tendencias y el dashboard InBody usan
`progress_dashboard._metric_points`: etiquetas en español,
inglés, acentos y secciones equivalentes se normalizan antes
de graficar. Para porcentaje de grasa se agrupan los tres
nombres ingleses confirmados en Neon, sin rellenar fechas
que genuinamente no tienen dato. Las unidades reconocidas
incluyen kg/kilogramos y %/percent/porcentaje; lb se convierte
a kg con un factor explícito solo en memoria y conserva
la fuente para auditoría. No suponer unidades vacías ni
interpretar medidas segmentales como totales. El formato
de nombre no obliga a hacer ninguna migración SQL.
El esquema de cuatro tendencias utiliza el primer examen
y las 10 fechas finales, las faltas se representan con
`None`, y el chat queda a la derecha.

Se retira `row_limits` de la tabla de revisión porque
la implementación actual de Gradio muestra que no opera.
La última fila no puede persistir si se elimina, porque
`save_audit` valida la tabla del lado servidor. E2E
requiere nueva validación de HF tras Python 3.12.


## Ajuste de alineación de minigráficas y chat (2026-11-03)

Se reemplaza la envoltura flexible de Gradio en
`#hj-coach-layout` por `display:grid !important`,
`grid-template-columns: minmax(260px,320px) minmax(0,1fr)`.
Las dos columnas Gradio se declaran con `min_width=0` y son
hijas directas del `gr.Row`: la primera contiene las cuatro
gráficas, la segunda el encabezado, el acordeón, el chatbot y
el composer. En anchos de 900 px o menos cambia a
`grid-template-columns:minmax(0,1fr)` y el panel se apila
encima del chat. Prueba estructural AST protege el nesting.

Las cuatro gráficas usan posiciones de examen como eje X, no
distancia entre fechas, para evitar que un examen antiguo
quede visualmente comprimido o parezca ausente. Los labels
del primer y último examen se fijan explícitamente;
la primera medición se destaca con rombo, y si no existe
su valor se deja `None` y se explica. Se conserva la regla
`primera fecha ∪ últimas diez fechas`, a lo sumo once fechas.
El chat conserva su lógica de mensajes y los consentimientos.
Ver `tests/test_coach_first_last_trends.py`.


## Panel compacto de tendencias junto al chat (propuesta)

En escritorio: una columna izquierda con cuatro gráficas de 140 px
de alto y el chat a la derecha. En móvil, panel encima del chat,
con desplazamiento interno a un máximo de 295 px. Orden fijo:
**Peso, Masa musculoesquelética, % grasa corporal, Puntaje InBody**.

Puntos visibles = primera prueba registrada + diez últimas fechas de
pruebas; nunca más de 11 fechas, sin repetir la primera si queda entre
las últimas diez. Se grafican en orden ascendente. La selección se hace
antes del filtro de medidas y no depende del período del chat; cada
métrica puede tener menos puntos si falta en una prueba. Las filas de
auditoría solo muestran fecha, no hora; misma fecha = una coordenada
temporal. Ver `inbody_mvp/coach_trends.py` y las pruebas
`tests/test_coach_first_last_trends.py`.
El botón Actualizar tendencias no llama a Gemini.


## Proyecto: entregables académicos del primer módulo (propuesta 2026-11-03)

Dentro del módulo Proyecto se incorpora el acordeón `Entregables académicos · Módulo 1`, no una ruta adicional. Tiene ocho campos editables ordenados según la actividad de Fundamentos de la Programación, nombre del autor, cuatro capturas PNG/JPG con pies explicativos, botón `Actualizar vista previa` y botón `Generar Word (.docx)` que proporciona el fichero descargable. Se precargan enlaces y contenido contrastado con el código del producto. Faltantes quedan visibles como pendientes y no se inventan evidencias de compañeros. No se guarda la edición en Neon; solo se exporta el Word de manera temporal.

Especificación: `docs/entregable-modulo1-obs.md`; código: `inbody_mvp/module1_deliverable.py`; prueba: `tests/test_module1_deliverable.py`.


## UI actual de cuatro módulos · 2026-11-03

**Menú vertical inicial:** Proyecto; Extractor de InBody; Captador de
logs de entrenamiento; Chat con el asistente fitness. No hay tab
independiente Historial ni selector de exportaciones CSV. InBody
muestra una **barra fija de cuatro etapas Cargar → Extraer →
Revisar → Guardar**, no cinco. Cuando Gemini termina se presenta
tabla editable a la izquierda del visor vertical de documento (se
apilan en móvil). El usuario puede corregir directamente, eliminar
filas con el control nativo Gradio y marcar `reviewed`; el único
botón **Guardar mediciones** valida y escribe. No hay botón de
validación previo. La pantalla se limpia **solo tras guardado correcto**.

El dashboard Plotly InBody se mantiene dentro del extractor, con
Score, fase angular, tendencias y secciones. FitNotes ofrece
importación, preview y consulta de series. El chat muestra burbujas
en secuencia, modelo independiente, metas/restricciones, historial
en sesión y lecturas privadas automáticas InBody/FitNotes.
Control de consentimiento previo al login, no checkboxes repetidos
en cada pantalla. Las pestañas CSV y la barra de cinco pasos que
aparecen en secciones antiguas son **LEGACY**.
Criterios en [00](00_estado_vigente_y_trazabilidad.md).


---


> **UI vigente (2026-11-03):** exactamente cuatro módulos en menú vertical: **Proyecto (inicial)**, **Extractor de InBody**, **Captador de logs de entrenamiento**, **Chat con el asistente fitness**. No hay `gr.Tabs` horizontales, menú de tres puntos ni tab separada «Historial». En InBody, el indicador de cinco pasos usa `position: fixed` en navbar externa al contenedor, navegación automática tras pasos exitosos y reset tras guardar; el dashboard Plotly está dentro del extractor. Training Hub importa FitNotes CSV, y el chat utiliza interfaz de burbujas con selector propio de Gemini. **La corrección de mensajes secuenciales y multiturno es PR #72 aún abierto**. Los diseños que siguen de «InBody Upload»/«Dashboard» como tabs y de selector CSV/Neon son **propuestas/legado**, no estado actual. [Criterios UX](00_estado_vigente_y_trazabilidad.md#3-matriz-de-aceptación-operativa).


Además de InBody, Gradio incorpora un módulo aislado para cargar
CSV FitNotes y almacenar series de entrenamiento de un usuario autenticado.
Incluye campo CSV, resumen de días/ejercicios, vista previa de 60 filas,
consentimiento específico, confirmación separada de sobrescritura, botón de
guardado en Neon y vista privada de últimas 60 series. Los CSV no se envían
a Gemini. Diseño de columnas adaptable y tabla desplazable en móvil.
El backend preserva decimales y valores negativos, evita duplicación por
archivo o posición de serie y no escribe sin autorización. El DDL se verificó en rama temporal y se aplicó a Neon principal con aprobación
expresa del usuario; aún falta merge y despliegue de la interfaz.
Guía: `docs/training-hub.md`.

## Archivo histórico: Gradio y dashboard de doble fuente (propuesta anterior)

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


## 1. Reglas de interfaz

- Toda la experiencia del MVP corre en `app.py` con Gradio `Blocks`; no introducir Dash.
- Idioma de la interfaz: **español**; no traducir etiquetas originales del reporte dentro del campo de procedencia.
- Cada acción indica claramente si los datos son candidatos, borrador CSV o examen confirmado.
- Las operaciones de Neon requieren sesión/autorización del lado servidor. El CSV puede analizarse **sin conexión Neon**, de acuerdo con la privacidad del entorno.
- No usar caches globales que mezclen sesiones o identidades. Al cambiar la fuente, descartar estado de la fuente anterior o mantenerlo aislado.

## 2. Pestaña «InBody Upload»

Campos y comportamiento:

| Componente | Comportamiento |
| --- | --- |
| Cargar archivo | PDF/JPG/JPEG/PNG, validación previa |
| «Extraer mediciones» | Invoca motor de extracción, muestra candidatos y advertencias |
| Metadatos | ID, equipo/modelo, timestamp, edad, origen de edad y `idioma_reporte` |
| Tabla editable | Literal, métrica, categoría, dimensión, segmento, frecuencia, unidad, valor, página y fuente |
| OCR / advertencias | Bloque expandible, no se publica en logs |
| **«Exportar CSV»** | Disponible con o sin Neon; conserva siete columnas y nombre único con hash+UTC |
| «Guardar examen confirmado en Neon» | Visible con estado disponible/deshabilitado, nunca escribe si faltan credenciales/autoridad |
| Resultado de guardado | Solo mostrar éxito cuando termina la transacción y devuelve ID interno |
| Limpiar | Borra datos y referencias temporales de la sesión |

**Orden recomendado:** Cargar → Extraer → Corregir → Exportar CSV **y/o** Confirmar/guardar en Neon.

## 3. Pestaña «Dashboard»

**Un solo dashboard**, dos orígenes seleccionables:

- `Neon PostgreSQL`: seleccionar persona y pulsar «Consultar Neon». Requiere OAuth y permisos; obtiene exclusivamente mediciones confirmadas.
- `Cargar CSV`: seleccionar uno o más archivos con `gr.File(file_count="multiple", file_types=[".csv"])`; combinar y validar en memoria, sin tocar Neon.

Mostrar origen activo en título/estado y nunca mezclar ambos silenciosamente. Datos con múltiples personas exigen elegir identificador. Mostrar: número de archivos, filas, métricas, fechas faltantes, filas rechazadas, duplicados y advertencias de comparabilidad. El importador de CSV debe rechazar otros formatos en lugar de asumir estructura.

### 3.1 Filtros

| Filtro | Regla |
| --- | --- |
| Persona | Un `id_persona` por consulta/gráfica, sin mezclar IDs |
| Fechas | Desde/hasta, sin inventar fechas de examen |
| Variable medida | Clave canónica, incluido desconocido si existe |
| Unidad | Igualdad exacta; no mezclar kg, lb, % o Ω |
| Modelo | Selección específica o vista multiserie separada por equipo |
| Segmento corporal | Brazo/pierna izquierda/derecha, tronco, cuerpo completo/sin segmento |
| Frecuencia kHz | Mostrar cuando exista; separar series de frecuencias conocidas y desconocidas |
| Tipo de resultado | Distinguir masa magra, músculo esquelético, porcentaje relativo a referencia y masa grasa |

Los selectores deben actualizarse a partir de los datos cargados y no ofrecer medidas que no existen. Un filtro sin resultados muestra mensaje y tabla vacía, no un gráfico falso.

### 3.2 Gráficos

- **Líneas temporales** con eje X = fecha/hora de examen; eje Y = valor y unidad declarados.
- Distintos modelos, unidades, semánticas o frecuencias no se conectan por una línea. Usar series separadas o advertir incompatibilidad.
- Grasa corporal kg vs masa muscular esquelética kg: comparación en el mismo panel solo cuando sea legítima y el significado esté marcado; grasa % vs masa magra kg debe mostrarse en gráficos o ejes diferenciados.
- Segmentos izquierda/derecha: comparar sus medidas compatibles y etiquetas inequívocas.
- Ángulo de fase: conservar región y kHz; si faltan, línea independiente «frecuencia no indicada».
- Grasa segmental y masa libre de grasa segmental: no atribuir cifras de porcentaje de referencia a porcentaje de composición real.
- Cada gráfico tiene tabla de datos correspondiente, con origen y modelo.

### 3.3 CSV multipágina / multiexamen

Al cargar 10 CSV, combinar observaciones del **mismo identificador** en orden cronológico. El historial se puede graficar aun cuando Neon no esté disponible. Informar claramente:
- archivos procesados y rechazados;
- registros únicos;
- duplicados por carga repetida;
- registros sin fecha (mostrables en tabla, pero no en la tendencia);
- valores inválidos;
- falta de metadatos en el contrato CSV v1.

**No** convertir la carga de CSV en una importación persistente por defecto.

## 4. Control de estado por sesión

- `gr.State` mantiene únicamente datos necesarios de la extracción/dataset durante la sesión.
- No publicar archivos temporales con nombres predecibles y contenido identificable; usar directorio protegido, nombres no sensibles y política de limpieza.
- El servidor debe verificar la identidad OAuth nuevamente en cada evento que lea/escriba Neon. La visibilidad de botones no es mecanismo de autorización.
- Los archivos CSV no deben subirse automáticamente a otra plataforma ni guardarse en Neon.

## 5. Estado implementado frente al estado objetivo

En `main` verificado el 31/10/2026:
- Carga/OCR, edición y exportación CSV v1: **código presente**.
- Conexión y guardado en Neon, tabla y gráfica inicial de consulta: **código presente**, dependiente de configuración/credenciales.
- Dashboard de varias fuentes (Neon + múltiple CSV): **pendiente**.
- Nombre CSV hash+timestamp exportación: **pendiente**.
- Validación real de Space y de datos sensibles: **pendiente**.
- Botón «Guardar» visible cuando falta configuración: trabajo separado en un PR; verificar estado antes de reconstruir.

Este documento describe la funcionalidad **que debe construirse** y no afirma que todas las opciones ya estén desplegadas.
