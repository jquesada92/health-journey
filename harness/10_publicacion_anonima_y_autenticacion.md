# 10 — Separación pública/privada, autorización y publicación de estadísticas

**Corte de código:** rama `main` posterior a los merges de los PR #8 y #9, verificado el 31/10/2026.

## 1. Decisión esencial: dos entornos, no un CSV identificado públicamente

La visualización pública solicitada no debe mostrar el identificador del reporte, el nombre de la persona, la fecha de nacimiento, la edad, archivos originales, texto OCR, hashes de origen ni registros individuales.

Quitar el ID **no garantiza anonimato**. Las mediciones individuales y sus fechas pueden facilitar reidentificación. Por eso el modelo público actual publica exclusivamente **estadísticas mensuales por cohortes** con consentimiento explícito, no tendencias de un paciente bajo un seudónimo. Los valores individuales permanecen en el entorno privado.

| Modalidad | Space previsto | Configuración | Funciones permitidas |
| --- | --- | --- | --- |
| Privada | `jaqo/health-journey` | `ENABLE_PUBLIC_DASHBOARD=0`, `DATABASE_URL`, `HF_ALLOWED_USERS`, `ENABLE_PERSISTENCE=1` | OCR/revisión, CSV de borrador, guardar y consultar historial privado previa autorización |
| Pública | **Otro Space separado, aún por crear/verificar** | `ENABLE_PUBLIC_DASHBOARD=1`, `PUBLIC_DATABASE_URL` | Leer únicamente vista agregada consentida mediante rol SQL de solo lectura |

**No habilitar ambas modalidades en un Space que recibe datos personales.** Aunque el modo público del código deshabilita botones y comprueba el acceso en callbacks, para datos reales debe crearse una aplicación pública mínima que **no registre endpoints de carga, OCR ni lectura privada**. Un botón deshabilitado no evita por sí solo que existan rutas de subida de archivos en Gradio.

## 2. Esquema y publicación

La migración **aditiva** está en `db/migrations/002_public_aggregate_dashboard.sql`.

- Campo: `hj_exams.public_release_approved_at TIMESTAMPTZ`, inicialmente `NULL`.
- Vista: `hj_public_monthly_summary`.
- Fuente: exámenes aprobados explícitamente y mediciones confirmadas.
- Agregación: primero promedio por persona/mes; luego promedio por cohorte.
- Granularidad de salida: mes, grupo de modelo sanitizado, métrica, unidad, región, frecuencia, participantes y promedio.
- Umbral de supresión: **al menos cinco personas distintas** por cada grupo. Evita grupos pequeños, pero no elimina todos los riesgos de inferencia/diferencias entre cohortes o períodos.
- Se excluyen nombres, IDs, UUID, edad, fecha exacta, reporte original y texto OCR.
- Lista cerrada de métricas: peso, músculo esquelético, grasa kg, grasa %, agua total, masa magra/grasa segmental y ángulo de fase.

**Consentimiento y revocación auditables aún no implementados**. No completar `public_release_approved_at` para datos reales hasta definir quién autoriza, cómo se registra y cómo se retira la publicación.

## 3. Credenciales distintas y mínimo privilegio

**Privado:**
- Secret `DATABASE_URL`: rol `health_journey_runtime` restringido y SSL.
- Variable `ENABLE_PERSISTENCE=1` solo tras verificar seguridad.
- Variable `HF_ALLOWED_USERS`: usernames de Hugging Face separados por coma (p. ej., `jaqo`), **no correos ni nombres visibles**.

**Público:**
- Secret `PUBLIC_DATABASE_URL`: connection string de `health_journey_public` con `sslmode=require`.
- Variable `ENABLE_PUBLIC_DASHBOARD=1`.
- **No proporcionar `DATABASE_URL` al Space público**.
- `health_journey_public` debe poder ejecutar `SELECT` únicamente en `hj_public_monthly_summary`, sin lectura/escritura sobre `hj_measurements` ni permisos administrativos.
- La existencia del rol no implica conexión utilizable: validar inicio de sesión, contraseña y permisos efectivos en Neon. **No guardar una contraseña en el repositorio.**
- En entorno privado mantener `ENABLE_PUBLIC_DASHBOARD=0`; sin configuración pública no hay publicación.

Nota operacional a fecha de creación: la vista SQL y el rol restringido se han creado en Neon, pero el proceso para publicar datos reales **no está activo**. No asumir que el Space separado existe o que la cadena de conexión pública ya está configurada.

## 4. Corrección de autenticación y carga (PR #7 y #8)

El código compara `HF_ALLOWED_USERS` con `gr.OAuthProfile.username`, **no** `name` (nombre visible).

En el callback `process_report`:
1. **Primero** comprobar si el archivo está presente; si falta, responder `Primero carga un PDF, JPG, JPEG o PNG.` sin consultar OAuth.
2. Con archivo presente, exigir acceso autorizado al flujo privado cuando existe allowlist.
3. Ejecutar extracción OCR, sin condicionar la operación a la conexión Neon.
4. Al exportar CSV privado, comprobar permisos de reporte, sin exigir conexión a PostgreSQL.
5. Al guardar o consultar datos individuales, comprobar OAuth y disponibilidad de Neon por separado.

**Limitación:** probar este orden en el código no demuestra que el OCR de JPG/PNG funcione en el runtime real de Hugging Face. Continúan siendo necesarias pruebas E2E con archivos **sintéticos o previamente anonimizados** y revisión de errores de EasyOCR/CPU/GPU.

## 5. Componentes y rutas

| Componente | Función |
| --- | --- |
| `inbody_mvp/public_dashboard.py` | Adaptador SQL público, solo métricas permitidas y `PUBLIC_DATABASE_URL` |
| `inbody_mvp/storage.py` | Acceso privado y comprobaciones OAuth |
| `db/migrations/002_public_aggregate_dashboard.sql` | Campo de autorización y vista agregada |
| `docs/dashboard-publico.md` | Detalle de permisos, políticas y operación |
| `app.py` | Pestaña pública y pestañas privadas del prototipo |
| `tests/test_public_dashboard.py` | Regresión sin datos personales; comprueba columnas, cohortes, acceso |
| `tests/test_ocr_runtime.py` | Errores de OCR y orden de validación al extraer sin archivo |

## 6. Despliegue recomendado y comprobación

1. Confirmar que `main` tiene los PR #7–9, y que el deploy del **Space privado** concluyó. No inferirlo por el merge.
2. Mantener `jaqo/health-journey` privado para cargas de reportes reales y confirmar su inicio de sesión.
3. Levantar un **segundo Space de solo visualización** sin registro de widgets/endpoints de carga; usar adaptador público únicamente.
4. Configurar `PUBLIC_DATABASE_URL` como Secret y la bandera pública como Variable, sin acceso a `DATABASE_URL`.
5. Probar en una BD de QA con grupos sintéticos de 4 y 5 sujetos: el grupo con 4 **no aparece**, el de 5 sí.
6. Probar que las consultas públicas rechazan métricas arbitrarias y que el rol público no puede consultar `hj_persons`, `hj_exams`, `hj_measurements` o `hj_measurements_long`.
7. Probar bloqueo de llamadas directas a endpoints privados, no solo botones deshabilitados.
8. Confirmar en Neon que **no hay exámenes publicados por defecto**.
9. Realizar evaluación de riesgo de reidentificación, consentimiento, revocación y revisión legal antes de publicación real.

## 7. Riesgos bloqueantes

- El Space público independiente **no se ha verificado** como implementado.
- Falta el flujo de consentimiento y revocación; poner el campo SQL a una fecha manualmente no equivale a consentimiento válido.
- El umbral de cinco participantes **no asegura anonimato absoluto**.
- La ruta de subida del prototipo Gradio debe eliminarse físicamente de una aplicación pública final.
- El dashboard de **múltiples CSV** y el nombre de exportación **hash + timestamp UTC** continúan pendientes según el código inspeccionado.
- Los resultados de CI son **sintéticos**, no sustituyen la prueba del Space con OAuth y credenciales reales.
