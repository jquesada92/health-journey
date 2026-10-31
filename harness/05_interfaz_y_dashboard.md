# 05 — Interfaz Gradio y dashboard de doble fuente

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
