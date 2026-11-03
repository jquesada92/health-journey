# 05 — Interfaz actual, navegación y dashboard

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
