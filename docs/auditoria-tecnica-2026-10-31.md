# Auditoría técnica — Health Journey / InBody Hub

> **Corte histórico fechado 2026-10-31:** esta auditoría no puede afirmar el estado actual de los módulos, consentimientos ni despliegue tras los PR #64–#70. Para el estado validado al 2026-11-03 usar [harness/00](../harness/00_estado_vigente_y_trazabilidad.md). Las conclusiones de octubre se conservan para trazabilidad, pero no son prueba de E2E ni autorización de cambios en Neon.


**Corte:** 31/10/2026 · **Repositorio:** `jquesada92/health-journey` · **Base de inspección:** `main` en `c9f609164bf23dd6469175adff7d525afbb84227`.

**Alcance:** revisión del código y workflows en GitHub, tests de CI en rama correctiva, y **metadatos de esquema/privilegios** de Neon. No se consultaron mediciones individuales ni archivos personales. **No se pudo verificar el runtime ni el último deploy efectivo de Hugging Face** con las herramientas disponibles.

## Resumen de resultados

| Área | Resultado | Evidencia |
| --- | --- | --- |
| Gradio, arranque | **FALLO BLOQUEANTE en main** | `app.py` usa `publication_choice` sin definición; el constructor de `gr.Blocks` puede lanzar `NameError` |
| Corrección candidata | **Validada en PR #12** | Restaura casilla `value=False`, la vincula a Guardar, y la reinicia al pulsar Limpiar |
| Tests del PR correctivo | **58 aprobados** | `Test InBody MVP` con `ruff --select F821` y prueba estática de Gradio; workflow `41250982572` |
| Harness CI | **Aprobado en PR #12** | Workflow `41250982594` |
| Neon / esquema | **Existente** | Vista privada `hj_measurements_long`, agregada `hj_public_monthly_summary`, individual `hj_public_person_series` |
| Neon / permisos públicos | **Verificados** | `health_journey_public` tiene SELECT sobre vista pública individual, NO SELECT/INSERT sobre `hj_measurements` |
| Datos publicados | **0** | 0 exámenes, 0 exámenes aprobados, 0 mediciones públicas al corte |
| OAuth | **Separación presente en main** | OCR y CSV pueden ejecutarse sin login; lecturas/escrituras privadas Neon requieren `OAuthProfile.username` autorizado |
| OCR PDF/JPG real en Hugging Face | **NO VERIFICADO** | Existen tests sintéticos, pero no una prueba E2E en el Space |
| Conexión pública desde Space | **NO VERIFICADA** | No fue posible consultar la configuración ni runtime de Hugging Face |

## Hallazgos priorizados

### P0 — Error de arranque del formulario de publicación

En `main`, `save_button.click(inputs=[..., publication_choice])` hace referencia a una variable inexistente. Las pruebas sintéticas existentes no hacían un chequeo de nombres indefinidos al construir la interfaz: `compileall` solo comprueba sintaxis.

**Corrección:** [PR #12](https://github.com/jquesada92/health-journey/pull/12). Además, añadir la casilla a Limpiar evita trasladar el consentimiento de un examen anterior al siguiente.

**Acción:** revisar y fusionar el PR, esperar CI verde y comprobar el nuevo despliegue en HF. No declarar resuelto en producción antes de que se abra Gradio y se guarde un examen sintético.

### P1 — Público y privado no están separados por aplicación

`app.py` contiene carga de documentos, OCR, CSV e historial privado **junto con** el visor público, aunque `ENABLE_PUBLIC_DASHBOARD=1` deshabilita controles y bloquea callbacks privados.

Deshabilitar controles **no elimina por sí solo** endpoints o superficies de subida del servidor. Para datos de salud reales es recomendable crear un Space/entrypoint público **solo lectura** que no registre operaciones privadas, y mantener ingestión en un Space privado.

**Acción:** separar frontend de solo lectura antes de publicar datos reales; confirmar secrets `DATABASE_URL` versus `PUBLIC_DATABASE_URL` de forma aislada.

### P1 — Publicación sin revocación desde la aplicación

`save_confirmed_exam(..., publish=False)` deja los exámenes privados por defecto, y una casilla permite autorizar publicación por examen. No se encontró flujo de revocación y auditoría en la interfaz.

**Acción:** permitir retirar consentimiento/examen publicado, verificar el efecto inmediato sobre la vista y registrar trazabilidad de la operación.

### P1 — Datos individuales solo seudonimizados

El alias es UUID aleatorio y **no** se deriva de la cédula/ID real; la vista pública limita columnas y la interfaz muestra alias abreviado. Sin embargo, la serie contiene valores y fechas de examen, que podrían permitir identificación indirecta.

**Acción:** etiquetar correctamente como seudonimización, documentar límites y evitar publicar reportes originales o texto OCR.

### P1 — Exportación CSV sin nombre solicitado

`download_draft` escribe un `NamedTemporaryFile` con prefijo `inbody_borrador_`. **No cumple todavía** el contrato solicitado `inbody_<hash>_<timestamp_utc>.csv`. El CSV continúa siendo un borrador con siete columnas.

**Acción:** generar hash del contenido, timestamp UTC y colisión segura; añadir pruebas de exportación y no alterar el contrato CSV.

### P1 — Dashboard privado con múltiples CSV pendiente

La pestaña «Dashboard (siguiente fase)» sigue siendo informativa. No se encontró la carga múltiple de CSV ni selector completo Neon/CSV especificado en el harness.

**Acción:** implementar importación múltiple validada en memoria, deduplicación, filtros y Plotly, **sin escritura a Neon**.

### P2 — Harness documental sin sincronizar

`harness/09_estado_y_decisiones.md` de `main` todavía no referencia la migración 003 ni el PR #11; parte de las especificaciones describen la vista pública solo por cohortes de cinco personas. Existe trabajo documental en otra rama, pero no se debe considerar actualizado `main`.

**Acción:** actualizar el harness con el flujo de publicación individual explícita, su condición por defecto privada, la revocación pendiente, las migraciones 002/003 y las correcciones recientes.

### P2 — CI no demuestra que Gradio y EasyOCR inicien en HF

El workflow prueba sintaxis, extractores y contratos con fixtures sintéticos; el PR #12 añade Ruff F821, pero no ejecuta un arranque E2E real del Space ni OCR con hardware real.

**Acción:** prueba smoke de construcción de Gradio con dependencias y OCR simulado, y pruebas manuales de JPG/PDF sintéticos en Hugging Face. Comprobar logs y commit desplegado en el Space.

## Pasos de aceptación antes de considerar el MVP operativo

1. Fusionar PR #12 después de su revisión; confirmar que se publica el commit correcto en Hugging Face.
2. Verificar que Gradio abre sin NameError y que la casilla Publicar está inicialmente desmarcada y se reinicia al Limpiar.
3. Cargar documento sintético en JPG y PDF, extraer, revisar y exportar CSV; comprobar que no se requiere OAuth para OCR/CSV.
4. Con sesión HF autorizada, guardar **dos** exámenes sintéticos: uno privado y otro con publicación marcada. Confirmar que solo el segundo llega a la vista pública.
5. Con el rol `health_journey_public`, comprobar SELECT únicamente de vistas autorizadas y denegación de lectura en tablas privadas.
6. Probar dashboard con `PUBLIC_DATABASE_URL` en una instancia pública separada, sin endpoints de ingesta.
7. Incorporar revocación y revisar el riesgo de reidentificación antes de publicar valores reales.
8. Implementar nombre CSV hash+UTC y dashboard multi-CSV pendientes.

**Conclusión:** el repositorio tiene una arquitectura funcional por módulos y 58 pruebas sintéticas verdes en la rama correctiva, pero **no está listo para declararlo probado de extremo a extremo**. El fallo de arranque detectado en `main` es bloqueante y tiene corrección propuesta en PR #12. El despliegue de Hugging Face y el flujo de publicación/revocación deben validarse antes de exponer datos reales.
