# Harness de reconstrucción — Health Journey

**Versión del contrato:** 1.0 — 31 de octubre de 2026  
**Idioma normativo:** español. Los nombres de tablas, variables, librerías y claves de datos se mantienen tal como exige el código.  
**Estado:** especificación de reconstrucción + inventario del MVP existente. No equivale a una certificación de producción.

## Propósito y alcance

Este directorio permite reconstruir Health Journey desde cero, auditar una instalación o transferir el desarrollo a otro equipo/agente sin consultar conversaciones anteriores. Es la referencia de producto y aceptación. Los archivos de código y el esquema real de PostgreSQL son la fuente de verdad del **estado implementado**.

La visión consiste en consolidar datos de salud y ejercicio provenientes de múltiples documentos y sistemas; el primer producto es **InBody Hub**. El MVP usa **Gradio, Plotly, Python, Pydantic, PyMuPDF y EasyOCR** con **PostgreSQL en Neon**. Hugging Face Spaces aloja la interfaz, con OAuth y ZeroGPU según disponibilidad. No utilizar Dash, Flask ni React para reconstruir la interfaz del MVP.

## Orden de lectura obligatorio

| Documento | Qué define |
| --- | --- |
| [01 — Producto y alcance](01_producto_y_alcance.md) | Objetivos, fases, historias de usuario, requisitos funcionales |
| [02 — Arquitectura y flujos](02_arquitectura_y_flujos.md) | Componentes, integraciones, límites y recorrido de datos |
| [03 — Modelo de datos y contratos](03_modelo_de_datos_y_csv.md) | PostgreSQL, métricas, CSV v1, nombres únicos, interoperabilidad |
| [04 — OCR e idiomas](04_extraccion_y_normalizacion.md) | ES/EN, InBody 580, otras plantillas, validación y trazabilidad |
| [05 — Interfaz y dashboard](05_interfaz_y_dashboard.md) | Pantallas Gradio, dos fuentes, filtros y líneas Plotly |
| [06 — Seguridad y privacidad](06_seguridad_y_privacidad.md) | Secretos, autenticación, datos sensibles y controles de acceso |
| [07 — Reconstrucción y operación](07_reconstruccion_y_operacion.md) | Pasos de instalación, Neon, Hugging Face, CI y recuperación |
| [08 — Calidad y aceptación](08_pruebas_y_criterios.md) | Matriz de criterios verificables, casos negativos y evidencia |
| [09 — Estado, decisiones y deuda](09_estado_y_decisiones.md) | Qué existe, qué falta, ADR y orden de implementación |
| [PROMPT_AGENTE.md](PROMPT_AGENTE.md) | Instrucciones listas para delegar la reconstrucción a un agente |

## Reglas normativas

1. **No inventar** fecha, hora, edad, nombre de variable, unidad, segmento, frecuencia ni valores.
2. Mantener en todo momento la distinción entre dato extraído, revisado y confirmado.
3. **Una medición = una fila.** Las nuevas métricas no crean columnas adicionales por equipo.
4. Detectar idioma del documento: `ES`, `EN` o `UNKNOWN`; conservar la etiqueta original y una clave de variable independiente del idioma.
5. Segmentar brazo/pierna izquierda/derecha, tronco y cuerpo completo, cuando el documento lo confirme.
6. No confundir masa muscular esquelética, masa libre de grasa, masa grasa y porcentaje relativo a referencia del dispositivo.
7. Admitir **ambas fuentes para el dashboard**: registros confirmados en Neon o múltiples CSV compatibles. Consultar CSV no debe provocar escrituras.
8. Preservar **Exportar CSV**, con nombre `inbody_<hash>_<timestamp_exportacion_utc>.csv`, sin datos identificables en el nombre.
9. No unir en una misma línea mediciones incompatibles por modelo, definición, unidad, región o frecuencia.
10. No registrar datos personales en logs, código, GitHub, pruebas públicas ni prompts.
11. Evitar cambios destructivos en Neon; ejecutar migraciones reproducibles y con control.
12. Nunca declarar una función «lista» sin pruebas y verificación de su entorno real.

## Prioridad cuando existen contradicciones

- **Intención funcional actual:** este harness y los criterios de aceptación (objetivo por construir).
- **Realidad del código:** `app.py`, `inbody_mvp/` y `tests/` en la rama/commit concreto.
- **Realidad de la base:** inspección de Neon + `db/schema.sql` + migraciones aplicadas.
- **Despliegue:** cabecera YAML de `README.md`, workflow GitHub Actions y logs del Space.
- Los textos antiguos de OBS/semana 2 en `especificacion.md` describen hitos históricos; no sustituir con ellos el estado actual.

## Estado de partida verificado al redactar

- GitHub: [`jquesada92/health-journey`](https://github.com/jquesada92/health-journey).
- Space: [`jaqo/health-journey`](https://huggingface.co/spaces/jaqo/health-journey).
- Neon: proyecto `health-journey`, base `health_journey`, PostgreSQL 17, región `aws-us-east-1`.
- Neon: `hj_persons`, `hj_exams`, `hj_measurements`, `hj_measurement_catalog` y vista `hj_measurements_long` verificadas. **Cero registros** al consultar el 31/10/2026.
- En `main` existen carga OCR, tabla editable, CSV de siete columnas, guardado condicionado a configuración y consulta inicial Neon.
- **Pendientes en `main` al crear este harness:** nombre de CSV con hash+hora de exportación; importación múltiple de CSV al dashboard; filtros unificados y endurecimiento de privacidad/roles.
- El trabajo de CSV/dashboard y de visibilidad del botón Guardar puede existir en ramas/PR independientes: revisar antes de implementar nuevamente.

## «Definición de terminado» del MVP

El MVP solo se considera recuperado cuando: (a) carga documentos compatibles, (b) devuelve candidatos trazables, (c) permite corregir y exportar CSV sin Neon, (d) puede guardar exámenes confirmados en Neon con autorización, (e) consulta Neon **y** importa varios CSV sin persistirlos, (f) genera gráficos de líneas correctamente segmentados, (g) respeta privacidad, y (h) pasa pruebas automatizadas y manuales. Ver [08 — Calidad y aceptación](08_pruebas_y_criterios.md).

**Ningún documento de este harness contiene credenciales, imágenes InBody reales ni resultados de salud identificables.**

## Actualización de publicación individual (migración 003)

Se añade al modelo objetivo la **publicación voluntaria de un historial individual seudonimizado**: conservar ID en tablas privadas, utilizar alias aleatorio `hj_persons.public_alias`, y consultar `hj_public_person_series` desde un lector público de solo lectura. No exigir una cohorte de cinco para un examen que el propietario aprueba explícitamente. La autorización inicial se efectúa mediante una casilla al guardar el examen en Neon, **desmarcada por defecto**; queda pendiente un mecanismo de revocación auditado y el Space público sin endpoints de carga. Las mediciones y fechas pueden permitir reidentificación. Más detalles: [`docs/public-person-series.md`](../docs/public-person-series.md).

## Decisión posterior: un solo Space para OCR y dashboard público

Por solicitud expresa del propietario, **el mismo Space de Gradio debe permitir carga y extracción PDF/JPG/PNG, exportar CSV y mostrar las series públicas**. Se elimina el bloqueo de controles cuando `ENABLE_PUBLIC_DASHBOARD=1`. El flag activa solo la lectura pública, no el modo de «solo visualización».

El servicio puede recibir **dos credenciales distintas**: `DATABASE_URL` para guardar/consultar Neon privado con OAuth verificado en servidor, y `PUBLIC_DATABASE_URL` para consultar exclusivamente vistas públicas con rol SQL de solo lectura. Las medidas publicadas usan alias UUID aleatorio y consentimiento por examen (desmarcado por defecto). No exponer el identificador del reporte, edad ni OCR en el dashboard público.

**Limitación aceptada:** en un Space públicamente accesible, cualquier upload envía sus bytes al servidor antes de que Python pueda anonimizarlo. Por tanto, solo cargar informes anonimizados **antes del upload** o utilizar un Space privado para datos de identidad. Este cambio no convierte series individuales seudonimizadas en anónimas irreversibles.

Los apartados históricos que prescriben dos Spaces ya no describen la configuración requerida actual; este contrato los sustituye. Las pruebas deben demostrar coexistencia de OCR/dashboard y bloqueo de operaciones SQL privadas sin OAuth.

## Corrección de login: pestaña OAuth independiente

Para evitar pantallas blancas al iniciar sesión desde la vista incrustada, se usa un enlace a `https://<SPACE_HOST>/login/huggingface` que abre en una pestaña nueva; el host se valida dentro de `inbody_mvp/oauth_ui.py` y nunca contiene secretos. El login solo es necesario para guardar/consultar Neon privado. El OCR, el CSV y las mediciones publicadas permanecen disponibles sin autenticar; el acceso de base privada se valida del lado servidor con `OAuthProfile.username`. Hay prueba sintética de URL segura y despliegue. La autenticación efectiva aún requiere prueba real en Hugging Face.

## Nueva capacidad para revisión académica: demo sin OAuth

`ENABLE_ANONYMOUS_DEMO=1` habilita el flujo de **carga → OCR → revisión → consentir almacenamiento → consentir publicación opcional → guardar en Neon → dashboard**, sin iniciar sesión. Se implementa en tablas/función SQL **aisladas** bajo rol `health_journey_demo_writer` sin derechos sobre la base privada de historiales. La decisión de publicar es diferente de aceptar almacenamiento; ambas casillas inician desmarcadas. No se publican ID, nombre, edad, texto OCR, fuente o archivos, pero sí fecha sin hora y medidas, que podrían ser indirectamente identificables. La vista demo caduca a los 7 días; la purga física y controles antiabuso más fuertes son trabajo operativo. En modo demo, los botones de historial privado se deshabilitan. Fuente: `docs/demo-anonima-consentimiento.md`, `db/migrations/004_anonymous_consented_demo.sql`, `tests/test_anonymous_demo.py`.
