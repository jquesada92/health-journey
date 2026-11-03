# 03 — Modelo de datos, nomenclatura y contratos de intercambio

## Canonización de timestamp desde nombre y reporte (propuesta)

Cuando `filename` cumple `^[^_]+_[0-9]{14}(?:[._-]|$)`,
el token es `AAAAMMDDHHMMSS` y se convierte a
`exam_datetime` de la extracción sin modificar el
nombre original ni el SHA-256. El reporte imprime
`DD.MM.AAAA HH:MM` y solo se utiliza como respaldo
si el nombre no trae el token. Se muestra la fecha
con segundos en la tabla de encabezado y se conserva
`raw_response` original con la lectura IA. Rechazar
año/mes/día inválido y no trasladar fechas de gráficas
históricas a un examen actual.

`migrations/011_correct_inbody_dates_from_filenames.sql`
corrige el timestamp histórico de `hj_extraction_audits`
sin tocar `hj_measurement_audits`. Antes de actualizar
cada cabecera, guarda ID técnico de extracción, nombre,
fecha original y fecha corregida en
`hj_exam_datetime_repair_history`. La vista privada
revisada deriva `exam_date` del header, por lo que
el análisis reflejará las fechas corregidas.
Es una migración de datos **pendiente de autorización y
ejecución**, no se aplica por publicar el PR.


## Reemplazo por archivo sin pérdida en errores (propuesta)

La captura InBody sigue en formato largo y con auditoría; ahora,
si se solicita explícitamente reingesta, la migración 010
`migrations/010_private_inbody_filename_replace.sql`
permite reemplazar **únicamente los registros activos** del
mismo `filename` (normalización trim/lower) y de la **misma
identidad canónica** del usuario autorizado. Los datos anteriores
se conservan en `hj_replaced_audit_backups` con snapshot completo
de la extracción y sus filas originales. La función PostgreSQL
`hj_replace_reviewed_audit_filename(jsonb,boolean)` valida
confirmación explícita, locks por archivo/hash/examen, colisiones
con otros archivos y propiedad del historial. Realiza backup,
DELETE de medidas/extracción antiguas y un INSERT mediante
el procedimiento validado `hj_submit_reviewed_audit` en una
única transacción. Cualquier excepción revierte todo el
reemplazo y deja el examen antiguo intacto. El archivo
corregido vuelve a tener un hash de origen único y no se
mezcla con capturas de otros documentos. DEMO_DATABASE_URL
no puede invocar este procedimiento.

**Estado:** SQL sólo versionado, aún no aplicado contra
`health_journey/main`. No se han modificado datos personales.


## Contrato vigente de persistencia, 2026-11-03

- **InBody**: encabezado único de examen e identidad; mediciones en
  filas largas con `measurement`, `section`, `value`, `unit`,
  `original_value`, `was_corrected`, `correction_comment` y
  `reviewed` para UI. No truncar `8.20` ni signos negativos. Solo
  se guarda al marcar reviewed y pulsar **Guardar mediciones**.
- **Neon InBody**: esquemas de base en `db/schema.sql`, auditoría
  `migrations/004–007`, vista privada revisada y controles de permiso.
  No equivale a un modelo de 7 columnas en pantalla.
- **FitNotes**: `migrations/008_fitnotes_training_hub.sql`;
  una fila por serie `owner_key/workout_date/exercise_key/set_number`,
  peso, unidad, reps, distancia y duración, con idempotencia.
- **IA semántica**: `hj_measurement_catalog` ya ampliado en Neon por
  migración 009, con 35 conceptos, 47 alias, 24 campos y comentarios.
  Lector en PR #84, no desplegado aún desde main.

El contrato CSV InBody de siete columnas descrito más abajo **es
LEGACY/portabilidad**, no un botón actual de exportación. Mantener
inmutabilidad de originales, normalización de unidades y separación
de datos personales frente a prompts. [11](11_cobertura_codigo_main.md)
lista cada DDL, script SQL y prueba.


---


> **Contratos reales (2026-11-03):** [inventario y criterios](00_estado_vigente_y_trazabilidad.md). El flujo Gemini devuelve `header(person_id,exam_datetime,age)` y `measurements(section,measurement,value,unit)`; `filename` viene del archivo. En la UI el encabezado aparece **una sola vez** y la tabla editable muestra mediciones con `original_value`, `was_corrected`, `correction_comment`, `reviewed`, sin `frecuencia_khz`. Los decimales se preservan como texto. La auditoría privada se modela con `migrations/004–007`; FitNotes usa `migrations/008_fitnotes_training_hub.sql` y 1 fila por serie. El contrato CSV de **7 columnas** y `db/schema.sql` siguen en el repositorio para compatibilidad, pero **no representan el formulario activo** ni una exportación CSV actual en la interfaz. Nuevos campos medidos deben agregarse como filas, nunca columnas especiales. La existencia de DDL no confirma su despliegue en Neon; no exponer auditorías por defecto. La normalización de persona no equivale a aislamiento multiusuario: permanece P0.



## Identidad InBody: vinculación privada y seudónimo en consultas

Un ID numérico con separadores, por ejemplo `88571257` y
`8-857-1257`, se normaliza a la misma clave interna `88571257`
(sin espacios ni guiones; **sin quitar ceros iniciales**).
Para IDs alfanuméricos se conservan los separadores y se estandariza
el uso de mayúsculas. Nunca se utiliza el número del reporte, ni su
hash determinístico, como alias visible.

La migración 005 crea `hj_person_aliases`: clave canónica **privada**
y un UUID aleatorio persistente `anonymous_id`. Al insertar cada
auditoría, la función asigna el UUID de la persona; dos informes con
el mismo ID normalizado comparten alias. El ID tal como aparece en
el PDF sigue conservado solo en `hj_extraction_audits.person_id`
y en el JSON original de auditoría, sin acceso público.

La vista `hj_audit_reviewed_private` devuelve solamente UUID,
**fecha sin hora**, sección, medición, valor, unidad y estado de
corrección. Excluye `person_id`, `filename`, edad, hora exacta y
`raw_response`. Su acceso se limita a roles privados; en Gradio,
`load_reviewed_audit_history` exige OAuth antes de consultar.
El formulario recibe el ID real en un campo visualmente oculto
y muestra únicamente `Persona <alias>` en tabla/gráfica.

El rol `health_journey_demo_writer` conserva permiso de **ejecución
de la función de inserción**, pero ninguno de lectura de alias,
mapa de IDs o auditorías. El dashboard público **no** consulta
auditorías privadas automáticamente: consentir almacenamiento en
Neon no constituye consentimiento de publicación. Exponer
tendencias individuales requeriría un consentimiento separado
y una revisión del riesgo de reidentificación. Un UUID es
*seudonimización*, no garantía de anonimato absoluto.

La migración 005 fue **aplicada a la rama main de Neon health_journey el
1 de noviembre de 2026** tras probarla en una rama temporal con IDs
sintéticos equivalentes. Se confirmó que dos formatos del mismo ID se
vinculan al mismo UUID aleatorio, el rol `health_journey_demo_writer`
puede ejecutar la función de escritura y los roles de demostración
y público **no** pueden leer las auditorías ni los IDs privados.
La instalación SQL quedó verificada; la aplicación todavía requiere
variables y Secrets correctos, consentimiento, revisión completa y
comprobación funcional end-to-end en Hugging Face.



## Contrato vigente de Gemini y auditoría (noviembre de 2026)

La respuesta Pydantic de Gemini contiene `header` (person_id,
exam_datetime, age), `measurements` (section, measurement, value, unit)
y `missing_or_unreadable`. Python obtiene `filename` del archivo original.
Cada una de las mediciones produce una fila con exactamente las columnas de
intercambio:

`exam_datetime, filename, person_id, age, section, measurement, value, unit`.

- `section`: sección del reporte, sin segmento corporal.
- `measurement`: etiqueta en español; para segmentos:
  `Brazo derecho - Masa magra`, `Brazo derecho - Frecuencia`.
- Frecuencia a 50 kHz: una fila de frecuencia (`50`, `kHz`) y
  otra fila de impedancia (`Brazo derecho - Impedancia a 50 kHz`, `Ω`).
- `Puntaje InBody` es una fila con unidad `puntos`.
- `value` permanece como **texto**, por ejemplo `8.20` y `0.370`.
- La fecha/hora es exclusiva del encabezado del examen actual;
  no se extrae información de `Body Composition History`.

**Auditoría separada, sin perder filas de origen:** `hj_extraction_audits`
conserva hash, filename, person_id, exam_datetime, age, modelo y JSON bruto.
`hj_measurement_audits` contiene una fila por medición, con
`original_section`, `original_measurement`, `original_value`,
`original_unit`, y sus versiones finales, `was_corrected`,
`correction_comment` y `reviewed_at`. Cuando una fila no cambió,
`was_corrected=false`; cuando cambió, requiere comentario. Las ocho columnas
se reconstruyen mediante join con la cabecera. **No es un cambio destructivo
de `hj_measurements` ni de la vista histórica de siete columnas**.

El nuevo contrato es el de Gemini y auditoría; las secciones siguientes sobre
el CSV de siete columnas describen compatibilidad *legacy*, no la salida
principal del InBody Upload. La migración SQL aditiva se encuentra en
`migrations/004_gemini_measurement_audit.sql` (distinta de
`db/migrations/004_anonymous_consented_demo.sql`).


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
