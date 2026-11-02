# Continuidad de InBody Hub — 1 de noviembre de 2026

> Registro de preservación de contexto, no certificación de implementación. **Solo documentación**. Consultar `AGENTS.md`, `harness/README.md`, `README.md`, los módulos Python, migraciones y PR concretos antes de modificar código.

## 1. Estado conocido y precauciones

- Producto: Health Journey; fase activa **InBody Hub**, interfaz **Gradio** en `app.py`, repositorio `jquesada92/health-journey`, Space `jaqo/health-journey`.
- La documentación de `main` describe extracción con **Gemini Flash** vía `inbody_mvp/gemini_review.py`, revisión por persona, consentimiento independiente para enviar a Gemini y para guardar auditorías en Neon; el modelo se utiliza por API, sin exigir GPU para extraer. El Space todavía emplea ZeroGPU y conserva un diagnóstico CUDA opcional para compatibilidad de arranque. No retirar `spaces` ni `gradio[oauth]` sin verificar despliegue alternativo.
- `README.md` documenta **Progress Dashboard** con indicadores Plotly y análisis por sección; es distinto de confirmar que todos los nuevos diseños, tendencias y comparativas solicitados ya se implementaron.
- `README.md` señala migración 005 de alias seudónimos aplicada a Neon el 2026-11-01 y el PR #38 fusionado. **No extrapolar** que otras migraciones, la cuenta de login, el build del Space o flujos E2E estén validados. Una indicación previa sobre migración 004 puede estar desactualizada: comprobar historial real de migraciones y funciones.
- Hay contenido heredado de OCR/EasyOCR/PaddleOCR, CSV y pruebas espaciales en el repositorio; las descripciones antiguas del harness no deben reactivar estas piezas por defecto. `especificacion.md` contiene hitos académicos históricos.
- No afirmar qué rama o Space están actualmente funcionales sin inspección del commit, estado de CI y pruebas. No incluir documentos reales, cédulas, credenciales ni resultados de salud en commits, logs o fixtures.

## 2. Contratos y decisiones que deben preservarse

1. **Una fila por medición** (`section`, `measurement`, `value`, `unit`) y metadatos del examen de origen. Nuevos tipos de medición agregan filas; no columnas ad hoc como `frecuencia_khz` en la tabla visible.
2. Fecha y hora del examen **del documento**, no del reloj del sistema. ID extraído con normalización controlada; no mezclar personas. La edad requiere fuente válida, sin inventar fechas de nacimiento.
3. Preservar el valor textual exacto, incluyendo ceros decimales: `8.20` no es `8`. No inferir valores ni unidades faltantes.
4. Modelo y contexto de medición: fase angular (global/segmental), frecuencia como medición/atributo semántico cuando aplique, región anatómica, lateralidad y unidades. Separar datos incompatibles en tendencias.
5. Distinguir valor del examen actual de gráficos históricos impresos. No extraer ni mezclar automáticamente esos puntos históricos.
6. La geometría de documentos importa: campos de encabezado con valor debajo del rótulo, tablas con etiquetas a la izquierda y números a la derecha. Preservar como decisión de diseño para futuros extractores espaciales; el motor actual usa Gemini y no está demostrado que el layout determinista esté activo.
7. La revisión humana tiene autoridad final antes de almacenar: permitir correcciones en sección, variable, valor y unidad; preservar original, indicador de cambio y comentario según contrato real.
8. Consentimiento para procesar con Gemini, consentimiento para almacenar en Neon y autorización de publicación **no son equivalentes**. Proteger datos privados; mantener autenticación y permisos mínimos, sin convertir auditorías privadas en datos públicos.

## 3. Solicitudes recientes pendientes de comprobación e implementación

| Prioridad | Solicitud | Criterio de aceptación / precaución |
| --- | --- | --- |
| P0 | Después de guardar correctamente, limpiar pantalla y estado del documento | Reset de editor, preview, nombre de archivo, mensajes y estado temporal **solo tras éxito confirmado**; no limpiar ante fallo. Restablecer consentimientos para documento nuevo. |
| P0 | Duplicado por nombre de archivo | Al reconocer un archivo ya procesado, informar directamente «Este archivo ya fue procesado». Definir alcance de identidad, hash de contenido y colisiones; no confiar en nombre por sí solo como prueba de igualdad de contenido. |
| P0 | Conflicto por ID persona + timestamp de examen + medición | Advertir que ya hay captura y pedir confirmación expresa para sobrescribir; definir política transaccional/idempotente, permisos, auditoría y si el sobrescrito realmente está permitido por el modelo de auditoría actual. **Nunca sobrescribir silenciosamente**. |
| P0 | Manejo unificado de errores | Mostrar **un solo popup por operación** con descripción útil, sin mensajes de error duplicados en cada componente; no filtrar secretos o datos personales. |
| P1 | Gráfico de línea de **InBody Score** | Historizar puntajes por fecha de examen; eje y con valor numérico correcto, fechas ordenadas y fuentes privadas autorizadas; evitar duplicados y mezclar personas. |
| P1 | Dashboard inspirado en el ejemplo InBody aportado | Indicadores y comparativas de grasa, músculo, agua y otras medidas existentes; incluir **ángulo de fase**, comparativas segmentales y gráfico histórico del puntaje. No copiar valores del diseño de ejemplo. Mantener unidades y compatibilidad entre mediciones. |
| P1 | Eliminar componentes no deseados del dashboard | La captura referida en conversación identificó un elemento a retirar, pero este registro no tiene un identificador textual inequívoco. Verificar la pantalla actual/captura antes de borrar componentes; no especular. |
| P1 | Selector de modelos **Gemini** | Mostrar solo modelos disponibles, aptos para lectura de InBody y susceptibles de uso gratuito según cuota, región y cuenta. Lista dinámica o configuración verificable; no prometer gratuidad perpetua ni cambiar a facturación sin autorización. |
| P1 | Secciones nuevas y correcciones en UI | Mantener visible el listado de secciones y refrescarlo tras edición/agregado/eliminación si ese flujo vuelve a estar activo. **No reintroducir el editor retirado** sin reconciliar con la arquitectura Gemini actual y autorización explícita. |
| P1 | Ángulo de fase | Mostrar sección/línea propia con descripción significativa, valor exacto y unidad; preservar frecuencia y segmento si proceden. |
| P1 | Extracción espacial robusta | Evaluar etiqueta sobre valor en encabezado y correspondencia izquierda/derecha en tablas; probar múltiples modelos y documentos anonimizados. No reemplazar el motor actual sin benchmark. |

## 4. Diseño, UX y persistencia: definiciones necesarias antes de cambios

- **Procesado vs guardado:** distinguir hash/nombre del documento, intento de extracción, revisión y transacción de auditoría exitosa. Un nombre idéntico con bytes distintos no debe confundirse con mismo contenido; una auditoría previa no equivale necesariamente a un examen consolidado.
- **Sobrescritura:** la auditoría original debe conservarse. Diseñar actualización versionada o reemplazo explícito de registro derivado con control de concurrencia; comprobar esquema y roles Neon antes de implementar. La frase de UX solicitada no autoriza un `DELETE` o `UPDATE` irreversible.
- **Dashboard:** reutilizar lectura privada filtrada y alias seudónimo, mantener separación del dashboard público. Se requieren fechas/hora suficientemente precisas y orden estable para una serie de puntaje; la vista privada actual documentada expone solo fecha, lo que puede generar empates intradía.
- **Modelos Gemini:** verificar nombres y disponibilidad actuales en documentación de Google; mostrar costos/cuotas como información dependiente del proveedor, manejar errores de cuota y permisos.
- **Errores:** la UI debe concentrar excepciones en un único punto, registrar detalles técnicos saneados y mostrar una sola notificación clara.

## 5. Criterios mínimos de validación al retomar

1. Dos cargas del mismo nombre y mismo hash; mismo nombre con hash distinto; un archivo nuevo con valores coincidentes; un mismo examen con variables nuevas.
2. Conflictos transaccionales por ID/timestamp/variable con confirmación, cancelación y fallo; verificar que no se pierden auditorías ni se mezclan personas.
3. Guardado exitoso limpia componentes; fallo mantiene correcciones y datos del usuario; el siguiente upload restablece consentimientos.
4. Un solo mensaje visible por error y sin duplicados en UI; ningún secreto/PII en errores.
5. `8.20`, porcentajes y valores segmentales sobreviven extracción, edición, auditoría, lectura y gráfica sin truncamiento.
6. Gráfico de puntaje con más de un examen, igual fecha, datos faltantes y cambio de modelo; compatibilidad y privacidad.
7. Variación de plantillas, rótulos de encabezado arriba de su valor y medidas izquierda/derecha sin capturar ejes o historial impreso.
8. En el Space: login, consentimiento de envío, carga, extracción, revisión, guardado, reinicio y dashboard, con evidencia verificable. Tests sintéticos no sustituyen validación E2E.

## 6. Reglas para los siguientes agentes

- Antes de editar: revisar `AGENTS.md`, este registro, `README.md`, `harness/09_estado_y_decisiones.md`, PR abiertos y cambios de `main`.
- Respetar el pedido actual de **documentación solamente**: ningún archivo de app, tests, SQL, requirements, workflow o configuración de despliegue debe modificarse en este cambio.
- Actualizar esta bitácora al cerrar cada requerimiento, especificando commit/PR, pruebas ejecutadas y evidencia del entorno; diferenciar claramente «solicitado», «implementado», «desplegado» y «validado».
- No hacer merge, despliegue, migración ni modificar secretos por el solo hecho de consolidar el contexto.

## 7. Nuevo requisito — diseño responsive mobile-first (solicitado 2026-11-01)

**Estado: solicitado, no implementado ni validado.** Toda la interfaz **Gradio** de InBody Hub debe adaptarse de forma usable a celulares, tablets y pantallas de escritorio; no sustituir la tecnología ni introducir una interfaz React/Dash paralela.

### Contrato funcional y visual

- Diseño **mobile-first** con una columna en pantallas pequeñas y distribución de dos columnas solo cuando haya espacio útil; sin scroll horizontal de la página.
- Navegación compacta, títulos y controles legibles; botones de carga, extraer, corregir, guardar y actualizar suficientemente grandes para uso táctil, con estados de carga y deshabilitado claros.
- En teléfono, cargar PDF/JPG/PNG desde archivos, cámara cuando el navegador lo permita; vista previa de páginas ajustada al ancho y con zoom/expansión. No ocultar consentimientos ni información crítica por falta de espacio.
- La tabla editable de mediciones debe conservar **todos los campos y precisión**; en móvil usar tarjetas de medición o editor de fila accesible (sección, variable, valor, unidad, original y comentario), en lugar de exigir desplazamiento horizontal de una tabla extensa. No duplicar editores en un mismo flujo.
- Dashboard adaptable: indicadores en cuadrícula flexible (1 columna móvil, más columnas en tablet/escritorio), filtros apilables, gráficas Plotly con ancho responsivo, ejes/etiquetas legibles y opción de inspeccionar valores; **InBody Score** histórico, ángulo de fase y análisis segmental deben verse correctamente en móvil.
- Mensajes de validación y el **único popup de error** visibles en pantalla pequeña, sin quedar tapados por teclado, cabecera o contenido flotante.
- Priorizar CSS/Gradio responsivo y componentes nativos; no bloquear la accesibilidad por estilos fijos ni comprometer autenticación/privacidad.

### Criterios de aceptación

1. Probar vistas de referencia de **360 px, 390 px, 768 px y 1280 px**; permitir zoom del navegador y orientación vertical/horizontal, sin desbordamiento general ni acciones invisibles.
2. Completar desde celular: login (si aplica), consentimientos, carga, visualización, extracción, edición de una medición, guardado y limpieza tras éxito.
3. Navegar dashboard, filtros, comparativas, gráficos y puntuación histórica con tacto; evitar recorte de leyendas, superposición de indicadores y pérdida de precisión decimal.
4. Verificar en Android Chrome y iOS Safari cuando estén disponibles; documentar cualquier limitación real de Gradio/navegador.
5. No considerar este requisito cumplido sin capturas o pruebas E2E en dimensiones móviles, además de las pruebas de escritorio.
