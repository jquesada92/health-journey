## Actualización propuesta 2026-11-02 — Training Hub FitNotes (rama, no producción)

- El MVP se expande con pestaña **Training Hub** en Gradio y módulo
  `inbody_mvp/training_hub.py`; **InBody Hub permanece separado**.
- Formato de entrada: CSV FitNotes de 10 columnas (Date, Exercise, Category,
  Weight, Weight Unit, Reps, Distance, Distance Unit, Time, Comment).
- 1 fila = 1 serie: conservar orden y duplicados reales, decimales y negativos.
- Importar solo con consentimiento y autenticación verificada en servidor;
  sin llamada a Gemini, sin publicación pública.
- Migración aditiva `migrations/008_fitnotes_training_hub.sql` probada en rama temporal y **aplicada a Neon principal con autorización
  del usuario**, sin importar ningún registro real.
- Idempotencia por hash de archivo + identidad de serie por dueño/fecha/
  ejercicio/posición. Si hay cambios, exigir casilla de confirmación.
- Código en rama `feature/training-fitnotes-neon-import-20261102`,
  todavía sin merge, despliegue o prueba E2E con credenciales reales.
- La importación del CSV personal recibido está **pendiente**.
- Guía operativa: `docs/training-hub.md`.

# 09 — Estado verificado, decisiones técnicas y deuda pendiente


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


**Fecha de corte documental:** 31/10/2026. El estado debe volver a verificarse contra el commit, Neon y los logs del Space en toda reconstrucción.

## 1. Inventario técnico confirmado

### GitHub
Repositorio: `jquesada92/health-journey`. Rama por defecto: `main`. El código consultado contiene:
- `app.py`: Gradio con lectura de PDF/JPG/PNG, tabla editable, CSV borrador, OAuth y funciones para Neon.
- `inbody_mvp/extractor.py`: texto PDF/OCR y clasificación conservadora.
- `inbody_mvp/layouts.py`: formato espacial InBody 580.
- `inbody_mvp/layouts_es.py`: formato español con siluetas.
- `inbody_mvp/language.py`: ES, EN, UNKNOWN.
- `inbody_mvp/review.py`: CSV de siete columnas.
- `inbody_mvp/storage.py`: guardado transaccional y lectura Neon con autorización.
- `db/schema.sql`, `tests/` y workflows GitHub Actions.
- `README.md` para metadatos de HF y documentación histórica.

### Neon
- Proyecto: `health-journey`, ID `autumn-pond-85488960`.
- Base: `health_journey`; PostgreSQL 17, región `aws-us-east-1`.
- Tablas comprobadas: `hj_persons`, `hj_exams`, `hj_measurements`, `hj_measurement_catalog`.
- Vista comprobada: `hj_measurements_long`.
- Estado de datos comprobado: **0 personas, 0 exámenes y 0 mediciones** al 31/10/2026.
- Rol previsto de la aplicación: `health_journey_runtime`, comprobar nuevamente permisos efectivos antes de uso.
- No asumir que el código de integración con Neon ya está funcionando dentro de HF sin prueba de extremo a extremo.

### Hugging Face
- Space objetivo: `jaqo/health-journey`.
- `sdk: gradio`, `app_file: app.py`, `hf_oauth: true` en README.
- Sincronización vía `Sync app to Hugging Face` en GitHub Actions.
- El hecho de que exista workflow no demuestra que el Space actual tenga la misma versión ni que tenga Secrets configurados.

## 2. Estado por capacidad

| Capacidad | Estado al corte | Qué falta para cerrar |
| --- | --- | --- |
| Carga PDF/JPG/JPEG/PNG | Código en `main` | Validar varias plantillas reales anonimizadas |
| OCR espacial / plantilla 580 | Código en `main` | Medir falsos positivos con OCR real |
| Plantilla española segmental | Código en `main` | Mayor cobertura de cifras difíciles |
| Idioma ES/EN/UNKNOWN | Código en `main` | Pruebas E2E de corrección |
| Tabla editable / CSV 7 columnas | Código en `main` | Verificar export/import en el entorno objetivo |
| Nombre CSV hash + UTC exportación | **Requisito nuevo pendiente** | Implementar y probar colisiones |
| Conexión/guardado a Neon | Código en `main` | Configurar entorno y completar prueba E2E segura |
| Botón Guardar visible sin conexión | **Revisar PR #4** | Confirmar merge y despliegue |
| Consulta y línea inicial desde Neon | Código en `main` | Corroborar autorización, datos y metadatos |
| Dashboard con carga de múltiples CSV | **Requisito nuevo pendiente** | Parser, unión, filtros y Plotly |
| Dashboard de fuente única seleccionable Neon/CSV | **Pendiente** | Unificar modelos/datos y UI |
| Almacenamiento de originales | **No implementado** | Diseñar política segura |
| Usuarios aislados mediante RLS | **No implementado** | Antes de multiusuario |
| Training/Nutrition/Medical | **Futuro** | Requerimientos y permisos propios |

## 3. Decisiones de arquitectura (ADR)

### ADR-001 — Gradio como única interfaz
**Decisión:** mantener Gradio `Blocks`, con `app.py` como punto de entrada y `gr.Plot` para Plotly.  
**Razón:** evita dos frontends, mantiene compatibilidad con Space/ZeroGPU y reduce mantenimiento.  
**Consecuencia:** no migrar a Dash/Flask/React sin una nueva decisión y autorización.

### ADR-002 — PostgreSQL en Neon para exámenes confirmados
**Decisión:** modelo relacional normalizado persona–examen–medición, catálogo bilingüe y vista long.  
**Razón:** integridad, historial persistente, consultas por persona/tiempo, crecimiento futuro.  
**Consecuencia:** migraciones, roles mínimos, transacciones y backup obligatorio.

### ADR-003 — CSV como contrato portable, no como dependencia de Neon
**Decisión:** mantener siete columnas y descarga siempre disponible.  
**Razón:** portabilidad y recuperación offline; minimiza dependencia de servicio.  
**Consecuencia:** CSV v1 no incluye todos los metadatos; la UI debe declarar esas ausencias.

### ADR-004 — Dashboard con fuentes alternativas
**Decisión:** misma UI puede consultar Neon **o** cargar múltiples CSV.  
**Razón:** resistencia a fallos del servicio e interoperabilidad.  
**Consecuencia:** normalizar ambos orígenes a un modelo de vista, no combinarlos silenciosamente ni persistir CSV por defecto.

### ADR-005 — Extracción conservadora y revisión humana
**Decisión:** OCR es asistente, nunca fuente confirmada de verdad.  
**Razón:** las plantillas heterogéneas pueden confundir números, ejes y segmentos.  
**Consecuencia:** conservar originales/indicadores de confianza en memoria, revisión obligatoria antes de guardar.

### ADR-006 — Idioma independiente de la clave de medida
**Decisión:** `idioma_reporte` vive en examen; las variables son canónicas.  
**Razón:** simplifica normalización ES/EN, comparación y catálogo bilingüe.  
**Consecuencia:** si no hay evidencia, `UNKNOWN` y corrección humana.

### ADR-007 — Privacidad y mínimo privilegio
**Decisión:** secretos fuera de código, OAuth de HF, rol SQL restringido, no exponer informes identificables en un Space público.  
**Razón:** datos personales de salud.  
**Consecuencia:** no declarar listo para producción sin controles de acceso, retención y auditoría.

## 4. Backlog priorizado tras la reconstrucción

1. **P0 — Seguridad:** confirmar Space privado y OAuth/allowlist, permisos de rol SQL, no PII en logs.
2. **P0 — CSV único:** implementar nombre basado en SHA-256 de contenido + UTC de exportación y evitar colisiones.
3. **P0 — Dashboard CSV:** cargar múltiple CSV v1, validación estricta, dedupe, aislamiento por sesión.
4. **P0 — Dashboard Neon + CSV:** selector de fuente y filtros consistentes sin escritura accidental.
5. **P0 — E2E:** prueba anónima de guardar Neon → consultar → exportar → CSV-dashboard, con conteos y permisos.
6. **P1 — OCR:** ampliar fixtures de plantillas y revisar precisión con OCR real sin datos públicos.
7. **P1 — Catálogo bilingüe:** poblar equivalencias verificadas de nombres ES/EN, unidades y comparabilidad.
8. **P1 — Migraciones:** establecer Alembic y versiones de esquema.
9. **P2 — Recuperación de históricos impresos:** parser específico, fechas inequívocas y deduplicación.
10. **P2 — Training/Nutrition/Medical/CDC Databricks:** fases posteriores.

## 5. Gestión de cambios y recuperación

- Cada modificación debe enlazarse a criterio `CA-xx` o `CS-xx` del documento 08.
- No afirmar que un PR «en revisión» equivale a código desplegado.
- Antes de implementar una función pendiente, buscar ramas/PR abiertos y verificar si ya existe trabajo.
- Mantener `harness/` y `AGENTS.md` sincronizados con decisiones nuevas.
- Las credenciales no forman parte de un «backup» de código; deben recrearse/rotarse por canales privados.
- Los reportes originales no están almacenados en Neon: reconstruir tablas no reconstruye automáticamente los archivos fuente.

## 6. Decisión experimental: detector de layout antes de OCR

**ADR experimental, no aceptación de producción.** Se propone reducir errores
de clasificación en documentos multicolumna colocando detección visual de
regiones antes de un segundo OCR por sección. La implementación de
`inbody_mvp/section_ai.py` y sus dependencias separadas
(`requirements-ai.txt`) residen inicialmente en una rama de evaluación;
**el flag `ENABLE_AI_SECTION_OCR` permanece desactivado por defecto**.

Razón: la extracción plana puede intercalar columnas, ejes gráficos y
mediciones históricas; el layout añade localización espacial. Alternativas:
continuar solo Regex + geometría (baseline) o estudiar un VLM documental
(opción futura, no implementada). Los costos de inferencia, la precisión real,
la seguridad y la compatibilidad de ZeroGPU no han sido evaluados.

**Decisión pendiente:** no fusionar/desplegar/activar el modelo solo porque
sus tests sintéticos estén verdes. Requiere benchmark privado con 22 reportes,
revisión manual de valores y reducción demostrable de falsos positivos.
El filtro actual de historial no cubre todo el flujo de OCR global.
Referencia: [Guía IA por secciones](../docs/ocr-secciones-ia.md).


## 7. Registro de continuidad — 2026-11-01

Se añade [10_continuidad_noviembre_2026.md](10_continuidad_noviembre_2026.md) como registro específico de las decisiones más recientes y de las solicitudes todavía por verificar/implementar. Prioriza distinguir **implementado en código**, **configurado/desplegado** y **validado E2E**. Esta incorporación documental no implica que las nuevas funciones ya existan, que los datos hayan sido migrados ni que se haya validado el Space.
