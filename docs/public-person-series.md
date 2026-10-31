# Publicar mi progreso InBody sin identificador real

## Comportamiento solicitado

Las **mediciones propias** (peso, grasa, músculo y medidas segmentales disponibles) pueden aparecer como líneas en el dashboard público, aunque la serie solo tenga una persona. **No se exige un mínimo de cinco personas para una tendencia individual**.

Al guardar un examen desde la **instancia privada**, el usuario autorizado puede marcar:

> Publicar las mediciones de este examen en mi dashboard público (sin mi ID)

La casilla viene **desmarcada**. La publicación se realiza en la misma transacción de guardado en Neon. Los demás exámenes siguen siendo privados, y un CSV o reporte cargado no se publica automáticamente.

### Qué muestra la vista pública

La vista `hj_public_person_series` permite únicamente:

| Columna | Explicación |
| --- | --- |
| `anonymous_id` | UUID aleatorio generado por PostgreSQL; **no** es hash del ID real, la cédula ni nombre |
| `exam_date` | Fecha del examen sin hora |
| `device_group` | Modelo de equipo sanitizado |
| `variable_medida` | Código canónico de la medición |
| `unidad_medida` | Unidad |
| `segmento` | Segmento corporal cuando corresponda |
| `frecuencia_khz` | Frecuencia de la medida cuando corresponda |
| `valor_medida` | Valor numérico |

La interfaz transforma `anonymous_id` en «Serie XXXXXXXX» y muestra líneas Plotly separadas por modelo, segmento, frecuencia y unidad. No muestra el identificador interno completo en la tabla visible.

**No incluye:** nombre, cédula/ID InBody, fecha de nacimiento, edad, hora, UUID interno, nombre/archivo del reporte, hash de origen, texto OCR ni etiqueta original. Tu ID real permanece en las tablas privadas para conciliar exámenes y nunca se selecciona en la consulta pública.

Esto es **seudonimización**, no anonimización irreversible: las fechas y valores publicados pueden identificar indirectamente a alguien que ya conozca su historial. El usuario toma la decisión de publicar cada examen expresamente.

## Arquitectura integrada en un solo Space

El mismo Space de Hugging Face puede procesar documentos, exportar CSV y visualizar el dashboard público:

- **OCR/CSV:** sin login; acepta únicamente reportes previamente anonimizados si el Space es público.
- **Guardar/historial privado:** usa `DATABASE_URL` del rol restringido; exige OAuth con usuario listado en `HF_ALLOWED_USERS`.
- **Dashboard público:** usa exclusivamente `PUBLIC_DATABASE_URL` de solo lectura y `ENABLE_PUBLIC_DASHBOARD=1`. Esta configuración **no bloquea** la selección de JPG/PDF ni OCR.
- Las dos cadenas de conexión se almacenan como Secrets diferentes. El frontend público nunca obtiene sus valores.
- **Privacidad:** los archivos se reciben íntegros antes del OCR; si contienen ID, nombre o DOB, su carga a un Space público sin login no es confidencial. Anonimizarlos **antes de subirlos**.

La migración `db/migrations/003_public_pseudonymous_series.sql` incorpora `hj_persons.public_alias` con `gen_random_uuid()` y la vista de tendencia individual, sin modificar las publicaciones existentes. `public_release_approved_at` se crea en migración 002.

## Activar y verificar

1. Ejecuta las migraciones 002 y 003 en Neon por un usuario autorizado (la 003 ya se aplicó a la base existente `health_journey` el 31/10/2026).
2. En el Space unificado, configura `DATABASE_URL` y `PUBLIC_DATABASE_URL` como **Secrets independientes**, y `ENABLE_PERSISTENCE=1`, `HF_ALLOWED_USERS` y `ENABLE_PUBLIC_DASHBOARD=1` como Variables.
3. Comprueba que `health_journey_public` solo tenga SELECT sobre vistas públicas. Guarda un reporte **sintético** con la casilla «Publicar» marcada únicamente cuando aceptes la visibilidad pública de sus valores y fechas.
4. Visita la pestaña «Dashboard público», elige variable y pulsa «Ver progreso público».
5. Si el resultado está vacío, comprueba si existe un examen guardado con publicación autorizada. La base actual no contiene todavía exámenes.
6. Para retirar una publicación hay que borrar la autorización `public_release_approved_at` del examen de manera autenticada y auditable; **todavía no existe botón de revocación en Gradio**, por lo que se requiere añadirlo antes de considerar el producto completo.

## Consultas de comprobación seguras

```sql
SELECT COUNT(*) FROM hj_public_person_series;

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'hj_public_person_series'
ORDER BY ordinal_position;
```

El rol público debe tener `SELECT` sobre la vista y **no** sobre `hj_persons`, `hj_exams` ni `hj_measurements`.

## Pruebas de aceptación

1. Un examen guardado con casilla desmarcada **no aparece** en la vista pública.
2. Un examen guardado con casilla marcada y un usuario autorizado aparece como una o más filas sin ID real.
3. Dos exámenes de la misma persona conservan un `anonymous_id` estable porque la clave aleatoria está en la persona, no en el examen.
4. Los valores de kg, porcentajes y frecuencias se muestran como series separadas.
5. Un usuario anónimo no puede guardar ni consultar `hj_measurements_long`; sí puede consultar solo datos previamente autorizados en el dashboard público.
6. El lector público no tiene permiso de leer, insertar ni borrar filas privadas.
7. Un documento con nombre/cédula nunca se ofrece como archivo público ni se usa para formar el alias.
