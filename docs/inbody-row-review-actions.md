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
3. **Eliminar:** selecciona cualquier celda de una fila y pulsa
   `Eliminar fila seleccionada`. No existen cuadros de texto ni
   botón alternativo para corregir una sola fila. Se conserva al menos
   una medición. La fila se excluye del examen pendiente, pero el JSON
   original de Gemini permanece intacto para auditoría.
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

No se admiten borrados o reordenamientos directos en la cuadrícula
porque impedirían vincular con seguridad el valor original y el
registro revisado. `remove_review_row` mantiene las filas retenidas
alineadas con la revisión y registra en memoria las descartadas.
No se modifican migraciones ni permisos de Neon.

## Pruebas y límites

Pruebas sintéticas de cambio de valor con autoselección, restauración
del original, intento de desmarcado manual, texto numérico negativo,
preservación de decimales, valor inválido corregible, y eliminación
tras correcciones en línea. El CI y las pruebas de despliegue
web/móvil son verificaciones separadas. No afirmar disponibilidad
en Hugging Face sin verificar el despliegue.
