# 09 — Estado verificado, decisiones técnicas y deuda pendiente

**Fecha de corte documental:** 31/10/2026; actualizado después de los merges de los PR #8 y #9. El estado debe volver a verificarse contra el commit, Neon y los logs del Space en toda reconstrucción.

## 1. Inventario técnico confirmado

### GitHub
Repositorio: `jquesada92/health-journey`. Rama por defecto: `main`. El código consultado contiene:
- `app.py`: Gradio con lectura de PDF/JPG/PNG, tabla editable, CSV borrador, OAuth y funciones para Neon.
- `inbody_mvp/extractor.py`: texto PDF/OCR y clasificación conservadora.
- `inbody_mvp/layouts.py`: formato espacial InBody 580.
- `inbody_mvp/layouts_es.py`: formato español con siluetas.
- `inbody_mvp/language.py`: ES, EN, UNKNOWN.
- `inbody_mvp/review.py`: CSV de siete columnas.
- `inbody_mvp/storage.py`: guardado transaccional, lectura Neon con autorización y validación de `OAuthProfile.username`.
- `inbody_mvp/public_dashboard.py`: consulta autorizada por configuración de estadísticos públicos agregados, con `PUBLIC_DATABASE_URL`.
- `db/migrations/002_public_aggregate_dashboard.sql`: marca de publicación explícita y vista `hj_public_monthly_summary`.
- `db/schema.sql`, `tests/` y workflows GitHub Actions.
- `README.md` para metadatos de HF y documentación histórica.

### Neon
- Proyecto: `health-journey`, ID `autumn-pond-85488960`.
- Base: `health_journey`; PostgreSQL 17, región `aws-us-east-1`.
- Tablas comprobadas: `hj_persons`, `hj_exams`, `hj_measurements`, `hj_measurement_catalog`.
- Vistas comprobadas: `hj_measurements_long` (privada, con identificador) y `hj_public_monthly_summary` (agregados sin ID).
- Estado de datos comprobado: **0 personas, 0 exámenes y 0 mediciones** al 31/10/2026.
- Roles: `health_journey_runtime` para el flujo privado y `health_journey_public` con permiso de solo lectura sobre la vista agregada. Verificar sus membresías, contraseña y permisos efectivos antes del despliegue.
- El último control de la vista pública mostró **0 grupos publicados**; no se deben convertir registros privados en públicos sin consentimiento auditable.
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
| Botón Guardar visible sin conexión | Código en `main` | Confirmar comportamiento y estado correcto en el Space |
| Consulta y línea inicial desde Neon | Código en `main` | Corroborar autorización, datos y metadatos |
| Validación sin archivo antes de OAuth (PR #8) | **Fusionado en `main`** | Verificar la ejecución en Space real; no implica que JPG/OCR funcione |
| Autorización por `OAuthProfile.username` (PR #7) | **Fusionado en `main`** | Confirmar sesión OAuth real con usuario de allowlist |
| Dashboard público de cohortes (PR #9) | **Código fusionado en `main`** | Crear Space público seguro separado, configurar `PUBLIC_DATABASE_URL`, completar pruebas E2E |
| Vista pública SQL y rol solo lectura | **Migración aplicada; rol creado** | Configurar credencial y revisar permisos efectivos; sin publicar datos privados |
| Consentimiento y revocación de publicación | **No implementado** | Diseño y pruebas auditables; bloqueante para publicar datos reales |
| Entry point público sin rutas de OCR/carga | **No implementado** | Desacoplar app pública de los callbacks de ingesta; bloqueante |
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

### ADR-008 — Separación entre dashboard privado y dashboard público

**Decisión:** dos Spaces distintos: uno privado para OCR/Neon/CSV individuales y otro público **sin rutas de ingesta** que solo lea agregados de `hj_public_monthly_summary`.

**Razón:** eliminar IDs de una serie no garantiza anonimato; el Space público no debe tener acceso a `DATABASE_URL` ni a datos privados.

**Consecuencia:** se requieren dos credenciales, consentimiento y revocación explícitos, reducción de riesgo de reidentificación y pruebas E2E. Cinco personas por cohorte es un mínimo de supresión, no garantía matemática de anonimato.

### ADR-009 — Validación de archivo antes de OAuth

**Decisión:** la función de extraer valida primero que hay un archivo, luego el acceso autorizado y después el OCR; no depende de Neon para extracción ni exportación.

**Razón:** un botón pulsado sin archivo debe informar el archivo faltante y no presentar falsamente un error de autenticación.

**Consecuencia:** mantener regresión que compruebe el orden de los callbacks y pruebas separadas de EasyOCR real.

## 4. Backlog priorizado tras la reconstrucción

1. **P0 — Seguridad:** confirmar Space privado y OAuth/allowlist, permisos de rol SQL, no PII en logs; crear entrypoint público SIN endpoints privados.
2. **P0 — CSV único:** implementar nombre basado en SHA-256 de contenido + UTC de exportación y evitar colisiones.
3. **P0 — Dashboard CSV:** cargar múltiple CSV v1, validación estricta, dedupe, aislamiento por sesión.
4. **P0 — Dashboard Neon + CSV:** selector de fuente y filtros consistentes sin escritura accidental.
5. **P0 — E2E:** prueba sintética de guardar Neon → consultar → exportar → CSV-dashboard, con conteos y permisos. **Verificar OCR JPG en Space real y validación sin archivo**.
11. **P0 — Publicación:** implementar consentimiento/revocación auditables, evaluación de reidentificación y despliegue separado con `PUBLIC_DATABASE_URL` de solo lectura.
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
