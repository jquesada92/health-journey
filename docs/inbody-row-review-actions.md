## Visor original junto a la tabla (3 de noviembre de 2026)

Tras seleccionar el PDF o la imagen, el visor integrado se prepara sin
invocar a Gemini. Una vez extraídas las mediciones, la pantalla de
revisión coloca **la tabla editable a la izquierda y el documento
original a la derecha** en escritorio. Ya no es necesario expandir
«Ver examen original» ni navegar a otro panel. El visor único muestra
todas las páginas del PDF, permite abrirlas en pantalla completa y
sigue siendo de solo lectura.

En escritorio el visor permanece próximo durante el desplazamiento de
la tabla. En tabletas y celulares (ancho inferior a 1100 px), el diseño
se apila: tabla primero y documento después, con desplazamiento
horizontal de las columnas sin comprimir las mediciones.

Se preservan: corrección directa en `value`, indicador
`was_corrected`, comentarios, exclusión nativa de filas, `reviewed`,
validación de `original_value`, consentimiento, deduplicación antes
de Gemini y guardado privado en Neon. El visor y su estado se limpian
después de un guardado exitoso. El cambio no altera el esquema ni
hace otra llamada al modelo.

**Pruebas:** contratos de Gradio sobre posiciones de columnas, visor
único no colapsable, páginas/PDF, flujo de reset y enlace del estado
de deduplicación al callback de extracción; CI y validación visual
en el Space son comprobaciones independientes.

## Presentación de errores — ajuste del 3 de noviembre de 2026

El navegador ya no debe mostrar pequeñas marcas o recuadros de error
por componente de Gradio: el estilo suprime únicamente
`div.validation-error`, sin ocultar el editor, los controles, los
rótulos ni el popup global. Las incidencias de extracción, cambios,
revisión y guardado se notifican por una sola alerta `gr.Warning`
cuando el usuario debe actuar.

La confirmación de la revisión mantiene su resultado interno oculto
para controlar el paso siguiente, pero una validación fallida borra
cualquier resultado de éxito anterior. Para archivos ya procesados
o no verificables se conserva solo el mensaje del archivo, sin un
segundo aviso redundante. La validación y la protección de auditoría
siguen ejecutándose: ocultar una marca visual no elimina controles
de integridad ni permisos.

**Verificación:** pruebas de contratos sintéticas y revisión visual
pendiente en Hugging Face, móvil y escritorio. El cambio no altera
persistencia Neon ni solicitudes Gemini.

# Revisión InBody: correcciones en la tabla y Guardar cambios

**3 de noviembre de 2026.** La revisión es un paso previo al guardado
de mediciones en la base de datos, y no modifica datos de Neon por sí sola.

## Flujo de usuario

1. **Editar:** las columnas `value`, `unit`, `section`,
   `measurement` y `correction_comment` se editan directamente
   dentro de la tabla. `original_value` se muestra bloqueada como
   evidencia inmutable de Gemini. El valor se maneja como texto para
   conservar, por ejemplo, `8.20`, `7.60` o `-0.370`.
2. **Casilla de corrección:** `was_corrected` ya no está bloqueada.
   Tras una edición se **recalcula automáticamente** comparando
   `value` (y otros campos de medición) con el original. Por seguridad
   una diferencia siempre la marca; al restaurar la medición original
   se desmarca. Marcarla sin que exista una diferencia no crea una
   corrección inventada. `reviewed` permanece bajo control manual.
3. **Eliminar:** utiliza el menú nativo de la fila en la propia tabla
   (con números de fila visibles). No hay selección ni botón externo
   `Eliminar fila seleccionada`. La acción de usuario se procesa a través
   del evento `Dataframe.input` de Gradio 6, tanto si edita valores como
   si elimina una fila. Se conserva al menos una medición y no se pueden
   añadir filas artificiales. La eliminación se aplica al examen pendiente,
   no a registros existentes de Neon; el JSON original de Gemini permanece
   intacto para auditoría.
4. **Guardar cambios:** único botón para **confirmar la revisión**.
   Valida el encabezado, los valores numéricos, notas obligatorias
   por cambios y las casillas `reviewed` de las filas conservadas.
   Un fallo se muestra en un aviso indicando la fila problemática.
   Una validación correcta avanza al paso 5. No escribe en Neon.
5. **Guardar mediciones revisadas:** acción distinta y explícita que
   persiste los datos en la base de datos, con comprobaciones de
   consentimiento, permisos y duplicados ya existentes.

## Integridad

`inbody_mvp/gemini_review.py::sync_review_corrections` es una función
pura que alinea el indicador con las diferencias de la revisión. Comprueba
cantidad de filas y `original_value` frente al snapshot inalterable;
no aplica coerción de valores numéricos, de modo que también permite
corregir después un valor inválido de IA. La misma regla se aplica
antes de validar y guardar, no solo al recibir eventos visuales.

Los borrados **directos en la cuadrícula** sí se admiten. La función
`reconcile_native_review_rows` empareja las filas restantes con
`original_value` y su orden original, utilizando las etiquetas de
sección, medición y unidad para distinguir valores repetidos. Actualiza
a la vez la tabla y el snapshot de auditoría, y conserva las mediciones
excluidas en memoria. Si dos fuentes son indistinguibles o alguien
reordena o modifica valores originales, rechaza la operación en lugar
de atribuir una medida a otra persona o segmento. La cuadrícula no
puede quedar vacía. `remove_review_row` continúa como compatibilidad
interna de backend, pero ya no requiere un botón en pantalla.
No se modifican migraciones ni permisos de Neon.

## Pruebas y límites

Pruebas sintéticas de cambio de valor con autoselección, restauración
del original, intento de desmarcado manual, texto numérico negativo,
preservación de decimales, valor inválido corregible, y eliminación
tras correcciones en línea, eliminación nativa por primera, última o
varias filas, valores originales repetidos y protección contra cambios
ambiguos de procedencia. El CI y las pruebas de despliegue
web/móvil son verificaciones separadas. No afirmar disponibilidad
en Hugging Face sin verificar el despliegue.
