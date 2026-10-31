# 03 — Modelo de datos, nomenclatura y contratos de intercambio

## 1. Principios

- Granularidad de **medición**: una fila por métrica observada, examen, segmento y frecuencia.
- Granularidad de **examen**: una evaluación con fuente y hora; el historial impreso de varias fechas en un solo reporte **no se convierte automáticamente** en exámenes sin extractor y pruebas específicas.
- Granularidad de **persona**: identificador interno distinto del ID impreso por el equipo; la conciliación entre proveedores debe ser explícita.
- Falta un dato → `NULL`/campo vacío. No sustituir por cero, promedio, hora inventada ni unidad esperada.
- Mantener la magnitud y la unidad por separado. Las referencias comparativas del dispositivo no son porcentajes de masa corporal.
- La identificación y autorización de la persona se gestiona por separado de la clasificación biométrica.

## 2. Modelo relacional implementado en Neon

| Objeto | Clave | Campos y comportamiento |
| --- | --- | --- |
| `hj_persons` | `person_uuid` UUID | `id_persona` del reporte, `source_namespace`, `birth_date` opcional, fecha creación; único en `source_namespace`+`id_persona` |
| `hj_exams` | `exam_uuid` UUID | `person_uuid` FK, `source_sha256` único, `modelo_inbody`, `machine_identifier`, `exam_timestamp`, `timezone_name`, `edad`, `age_source`, `idioma_reporte`, `language_basis`, `source_type` |
| `hj_measurements` | `measurement_uuid` UUID | `exam_uuid` FK, `row_number`, `variable_medida`, `original_label`, `categoria`, `dimension`, `segmento`, `frecuencia_khz`, `unidad_medida`, `valor_medida`, `pagina`, `extraction_source`, `confirmation_status` |
| `hj_measurement_catalog` | `canonical_code` | `display_label_es`, `display_label_en`, categoría, dimensión, unidad canónica y regla de comparabilidad |
| `hj_measurements_long` | Vista | Exactamente siete columnas de exportación analítica, obtenidas con joins de persona/examen/medición |

El DDL completo está en [`db/schema.sql`](../db/schema.sql). No duplicar manualmente su lógica sin verificar si hay migraciones posteriores.

### Restricciones importantes

- `hj_exams.source_sha256` único evita importar dos veces el mismo archivo fuente.
- `hj_measurements` usa única `(exam_uuid, row_number)`; una métrica repetida en distintas regiones o frecuencias es legítima.
- `idioma_reporte` solo admite `ES`, `EN` y `UNKNOWN`.
- `edad` debe estar entre 0 y 120, con procedencia indicada.
- `valor_medida` es numérico; estado de revisión y unidades no deben perderse.
- El `timestamp` del documento puede no tener zona horaria; guardar el origen y evitar convertir fechas locales suponiendo UTC.

## 3. Contrato CSV InBody v1 (obligatorio)

Encabezado exacto en este orden:

```csv
id_persona,modelo_inbody,timestamp,variable_medida,unidad_medida,valor_medida,edad
```

Ejemplo **sintético**, no correspondiente a ningún usuario:

```csv
id_persona,modelo_inbody,timestamp,variable_medida,unidad_medida,valor_medida,edad
PERSONA_DEMO,InBody 580,2026-01-15T09:30:00,weight,kg,72.4,30
PERSONA_DEMO,InBody 580,2026-01-15T09:30:00,body_fat_percentage,%,20.2,30
PERSONA_DEMO,InBody 580,2026-01-15T09:30:00,phase_angle__left_leg__50khz,°,6.1,30
```

Reglas:

1. Texto UTF-8 (se admite BOM en lectura); valor decimal finito, con punto en exportación.
2. `timestamp` ISO 8601 local cuando se conozca fecha y hora; en caso contrario vacío y sin posición en eje temporal hasta corregirse.
3. `variable_medida` es la clave normalizada, no la etiqueta española/inglesa del documento.
4. Si la medición es segmental, añadir sufijo al identificador: `__left_arm`, `__right_arm`, `__left_leg`, `__right_leg`, `__trunk` o `__whole_body`.
5. Para frecuencias especificadas en el reporte, añadir `__50khz`, `__100khz`, etc., **después** del segmento, cuando lo haya. No asumir una frecuencia que no esté impresa.
6. `unidad_medida` se conserva como origen; no efectuar conversiones automáticas no verificadas.
7. CSV v1 no contiene idioma, procedencia detallada o modelo de columnas segmentales adicional. Cuando se importe, preservar lo que sí exista; no atribuir al CSV metadatos que no lleva.
8. Campos de texto deben protegerse contra inyección de fórmulas en hojas de cálculo, sin corromper el uso analítico al reimportar.
9. CSV exportado es un **borrador revisable**, salvo que otro proceso explícito lo identifique como confirmado. Cargar CSV en dashboard **no** lo confirma automáticamente en Neon.

## 4. Nombre único del archivo exportado — requisito nuevo

Formato canónico objetivo:

```text
inbody_<sha256_contenido>_<AAAAMMDDTHHMMSSffffffZ>.csv
```

Ejemplo ficticio abreviado solo para ilustrar:

```text
inbody_61ac9804c35e0f12_20261031T215355123456Z.csv
```

**Implementación recomendada:** calcular SHA-256 sobre los bytes exactos del CSV exportado, usar al menos 16 caracteres hexadecimales del hash como identificador legible (o 64 si se quiere identidad completa), agregar hora **UTC con microsegundos**; escribir con exclusión de sobreescritura y, en el evento improbable de colisión, reintentar agregando identificador aleatorio. El hash de contenido aporta identificación/detección, no protege la privacidad ni garantiza unicidad por sí solo. El timestamp debe representar el **momento de exportación**, no la fecha del examen. No colocar cédula, nombre, documento fuente ni edad en el nombre.

Debe seguir siendo posible exportar aunque `DATABASE_URL` no esté configurada.

## 5. Importación de múltiples CSV al dashboard

- Interfaz `gr.File(file_count="multiple", file_types=[".csv"])`.
- Leer exclusivamente CSV compatible con el contrato anterior, con límite configurable de archivos, bytes y filas.
- Validar encabezados, codificación UTF-8, tipos, valores finitos y fechas.
- Combinar filas en una tabla común, conservar referencia del archivo, y **deduplicar duplicados idénticos**. No fusionar exámenes solo por misma fecha o peso si falta prueba de identidad.
- Usar ID exacto para distinguir personas y mostrar selector si hay varias. No unir identificadores diferentes automáticamente.
- Descomponer segmentos y frecuencia de los sufijos únicamente cuando se ajusten al contrato; otras claves quedan intactas.
- Si faltan timestamp/modelo/edad, permitir vista tabular pero señalar que no se puede representar esa fila en gráfico temporal.
- **No guardar en Neon**, no asociar a personas de Neon sin conciliación y no subir a almacenamientos externos.
- Filtros por fecha, persona, métrica, unidad, modelo y región. La frecuencia se usa para diferenciar series y puede exponerse como filtro específico.
- Si se cargan 5 archivos y 3 son copias exactas de otros, informar cuántas filas únicas y duplicadas se identificaron.

## 6. Correspondencia semántica de métricas

| Clave canónica | Interpretación | Unidad esperada solo si aparece en la fuente |
| --- | --- | --- |
| `weight` | Peso corporal | kg o lb |
| `body_fat_mass` | Masa de grasa corporal | kg |
| `body_fat_percentage` | Grasa corporal expresada como porcentaje de composición | % |
| `skeletal_muscle_mass` | Masa muscular esquelética | kg |
| `segmental_lean_mass` | Masa magra segmental, **no equivalente** a músculo esquelético | kg |
| `segmental_fat_mass` | Masa grasa de segmento | kg |
| `segmental_lean_reference_percentage` | Porcentaje relativo a referencia de masa magra | % referencia |
| `segmental_fat_reference_percentage` | Porcentaje relativo a referencia de grasa segmental | % referencia |
| `total_body_water` | Agua corporal total | L |
| `visceral_fat_area` | Área de grasa visceral | cm² |
| `ecw_tbw_ratio` | Relación de agua extracelular sobre total | proporción |
| `phase_angle` | Ángulo de fase | grados, segmento/frecuencia cuando consten |
| `impedance` | Impedancia | Ω y kHz cuando consten |
| `sin_clasificar__...` | Variable no normalizada, preservada con su etiqueta original | la observada o desconocida |

Añadir nuevas métricas al catálogo, **no modificar el significado de una clave existente** para encajar otra plantilla.

## 7. Normalización futura

El catálogo bilingüe debe almacenar nombres en español e inglés, categoría, dimensión, unidad canónica **y regla de compatibilidad**. La detección de idioma no autoriza convertir kilogramos a porcentajes ni equiparar reportes de modelos distintos. Las conversiones, si se implementan, deben ser explícitas, trazables, validadas y reversibles.

## 8. Consulta SQL de verificación

```sql
SELECT id_persona, modelo_inbody, "timestamp",
       variable_medida, unidad_medida, valor_medida, edad
FROM hj_measurements_long
ORDER BY "timestamp" DESC
LIMIT 100;
```

Los datos de pacientes **no deben aparecer en los logs de CI ni en archivos de fixtures**.
