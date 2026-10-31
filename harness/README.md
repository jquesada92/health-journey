# Harness de reconstrucción — Health Journey

**Versión del contrato:** 1.1 — 31 de octubre de 2026 (sincronizada con los PR #8 y #9)  
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
| [10 — Publicación, anonimización y OAuth](10_publicacion_anonima_y_autenticacion.md) | Spaces privado/público, vista de cohortes, consentimiento y errores al extraer |
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
13. Separar el Space de ingestión privada del Space de estadísticas públicas: ninguna serie individual se publica por ocultar su ID.
14. Solo publicar métricas agregadas y explícitamente autorizadas; el umbral de cinco personas no garantiza anonimato absoluto.

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
- **Ya fusionado en `main` (PR #7 y #8):** autenticación mediante `OAuthProfile.username`, procesamiento OCR independiente de Neon, y validación del archivo ausente *antes* del login.
- **Ya fusionado en `main` (PR #9):** `inbody_mvp/public_dashboard.py`, vista `hj_public_monthly_summary`, modo público de estadísticas agrupadas y bloqueo de funciones privadas en callbacks. **No equivale a publicación productiva**: falta consentimiento auditable, instancia pública separada y prueba E2E.
- **Pendientes:** exportación CSV con hash+timestamp UTC, carga múltiple de CSV en el dashboard, control y reconciliación de datos, endpoint público sin rutas de ingesta.
- Los datos privados y los agregados públicos tienen credenciales diferentes; consulta el documento [10](10_publicacion_anonima_y_autenticacion.md).

## «Definición de terminado» del MVP

El MVP solo se considera recuperado cuando: (a) carga documentos compatibles, (b) devuelve candidatos trazables, (c) permite corregir y exportar CSV sin Neon, (d) puede guardar exámenes confirmados en Neon con autorización, (e) consulta Neon **y** importa varios CSV sin persistirlos, (f) genera gráficos de líneas correctamente segmentados, (g) respeta privacidad, y (h) pasa pruebas automatizadas y manuales. Ver [08 — Calidad y aceptación](08_pruebas_y_criterios.md).

**Ningún documento de este harness contiene credenciales, imágenes InBody reales ni resultados de salud identificables.**
