# Revisión InBody: corregir/eliminar filas y un solo botón de validación

**3 de noviembre de 2026 — propuesta para revisión en GitHub.**

## Experiencia
1. Tras la extracción, revisa la tabla, incluidas las mediciones cuyo
   valor de IA no sea un número (por ejemplo «sin lectura»).
2. Para corregir un valor que no se puede editar cómodamente en la tabla,
   abre «Corregir o eliminar una fila», selecciona una celda de esa fila,
   introduce el valor numérico **como texto** (preserva signos y decimales,
   como `-0.370` o `8.20`), explica el motivo y pulsa
   **Aplicar corrección**. No se autoaprueba la fila.
3. En ese mismo panel puedes pulsar **Eliminar fila seleccionada**.
   Esto la retira solo de la revisión del examen actual, no borra
   datos ya persistidos en Neon. Se conserva el JSON original enviado
   por Gemini en `raw_response` y la copia original permanece en sesión.
   Se exige conservar al menos una medición.
4. Pulsa **Validar revisión** una sola vez tras marcar `reviewed`
   en las filas restantes. El proceso comprueba encabezado, números,
   revisión y comentarios. Si falla, muestra la fila afectada.
5. **Guardar mediciones revisadas** mantiene las comprobaciones
   originales de consentimiento, permisos y duplicados.

La validación sustituye las dos acciones consecutivas anteriores
«Continuar a validación» + «Validar revisión». La barra de progreso
conserva las 5 etapas: el resultado exitoso avanza a Guardar.

## Integridad y límites
El backend elimina la fila tanto del dataframe de revisión como del
snapshot de filas retenidas, preservando los campos de referencia y el
`raw_response` original de la IA. El usuario no puede editar
`original_value` ni borrar todos los registros. Un borrado efectuado
directamente mediante herramientas nativas del dataframe que no pase
por el control **Eliminar fila seleccionada** no se acepta porque no
garantiza la correspondencia de filas auditadas.

El estado y la eliminación se limitan a la sesión y a ese examen.
No se modifica el esquema de Neon, ni los consentimientos o el
documento fuente; no se hace ninguna escritura hasta guardar.

## Validación
Pruebas sintéticas: negativos, ceros decimales, valor de IA inválido,
eliminación de primera/fila intermedia, conservación de procedencia,
rechazo de índice inválido, protección de última fila, y único botón.
Se requiere CI y verificación manual en el Space y móvil antes de
considerar desplegado este cambio.
