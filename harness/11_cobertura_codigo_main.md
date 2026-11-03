# 11 — Inventario completo de `main` y cobertura documental

## Estado de la migración 011 (Neon, 2026-11-03)

`migrations/011_correct_inbody_dates_from_filenames.sql`
**ya se aplicó y validó en Neon** (17/17 encabezados,
1.087 filas asociadas, 0 diferencias, 17 backups), aunque
la migración sigue sin existir en `main` hasta la
fusión de este PR. `migrations/010_private_inbody_filename_replace.sql`
**NO está aplicada** y no debe presuponerse activa
en el Space. Los tests de PR #89 pasaron (424),
y la auditoría estática del harness aprobó.


## Cambio pendiente de merge: dos formatos de fecha InBody

`inbody_mvp/filename_timestamp.py` añade dos normalizadores:
`exam_datetime_from_filename` para `AAAAMMDDHHMMSS`
después del primer `_` y
`normalize_report_exam_datetime` para encabezado
`DD.MM.AAAA HH:MM`/variantes imprimibles. Se
conecta en `inbody_mvp/gemini_review.py`,
`inbody_mvp/upload_preflight.py` y se documenta
en `inbody_mvp/prompts/inbody_extraction.md`.
Se incorpora en allowlist
`.github/workflows/deploy-huggingface.yml`.
`tests/test_inbody_filename_timestamp.py` y
`tests/test_exam_timestamp.py` protegen los
formatos. `migrations/011_correct_inbody_dates_from_filenames.sql`
archiva fechas antiguas y corrige cabeceras en una
transacción solo tras autorización; no hay modificación
automática de datos en Neon. El inventario anterior
es un corte histórico de `main`, no la rama
en desarrollo.


## Cambio pendiente de merge: reingesta de archivo InBody

Se incorpora `migrations/010_private_inbody_filename_replace.sql`,
procedimiento privado de reemplazo atómico por nombre y copia
de recuperación `hj_replaced_audit_backups`; nuevo contrato
`tests/test_inbody_filename_replacement.py` en la suite CI.
Cambios relacionados en `inbody_mvp/upload_preflight.py`
(autorización y estado de archivo duplicado),
`inbody_mvp/gemini_review.py` (guardar reemplazo por
`DATABASE_URL` privado), `app.py` (checkbox opt-in
y un único botón Guardar), tests existentes de revisión,
`README.md`, `AGENTS.md` y harness. El inventario
corresponde al main histórico; estos archivos nuevos
se documentan en esta sección hasta su integración.
No se aplica automáticamente migración ni DELETE en Neon.


## Propuesta 2026-11-03 — normalización InBody y avisos HF

La auditoría anterior se conserva como corte de `main`.
El PR de correcciones modifica `app.py` (elimina
`row_limits` no operativo), `README.md` (YAML
`python_version: "3.12"`), `inbody_mvp/progress_dashboard.py`
(alias multilingües y transformación de unidades solo para
Plotly), `inbody_mvp/coach_trends.py` (nombres de InBody
Score ES), `tests/test_inbody_row_actions.py` y agrega
`tests/test_inbody_multilingual_trends.py` (regresiones
de compatibilidad y equivalencia entre formatos).
La suite `.github/workflows/test-inbody.yml` incluye
la nueva prueba. No modifica datos personales de Neon
ni requiere migración de esquema.


## Nueva cobertura pendiente de merge: tendencias en Chat

Nuevo archivo `inbody_mvp/coach_trends.py`: lector InBody autorizado,
selección SQL del primer examen y de los últimos diez, deduplicación
por fecha, 4 minigráficas Plotly y estados vacíos. Nuevas pruebas:
`tests/test_coach_first_last_trends.py`. Se actualizan
`inbody_mvp/progress_dashboard.py` (alias ES de variables),
`inbody_mvp/coach_chat_ui.py` (CSS responsive),
`app.py` (dos columnas y autocarga/refresh),
`.github/workflows/deploy-huggingface.yml` (allowlist) y
`.github/workflows/test-inbody.yml` (test). No se requiere
migración SQL y las reglas de privacidad existentes se mantienen.
La matriz histórica de archivos de main permanece intacta hasta
integrar este PR.


## Nueva sección académica del Módulo 1 (cambio propuesto, todavía no en main)

El inventario anterior corresponde al corte histórico de main del 03/11/2026. El PR de entregables añade los siguientes archivos al producto: `inbody_mvp/module1_deliverable.py` (contenido guiado, vista previa y DOCX), `tests/test_module1_deliverable.py` (validación sintética de ocho apartados y cuatro capturas), `docs/entregable-modulo1-obs.md` (especificación académica y criterios tomados del HTML proporcionado). Se conecta en `app.py`, añade `python-docx` a `requirements.txt` y amplía las allowlists de CI y despliegue de `.github/workflows/test-inbody.yml` y `.github/workflows/deploy-huggingface.yml`.

Este editor se presenta dentro de Proyecto, sin crear un quinto módulo; no consulta Neon ni envía borradores a Gemini. La fuente recibida es la instrucción HTML y no el DOCX de plantilla Blackboard: reproduce los ocho apartados y los requisitos, pero no afirma ser la plantilla visual original. Los campos del autor y cuatro imágenes son evidencias pendientes del alumno. No guardar ediciones tras refrescar es una limitación explícita de la versión propuesta.


**Corte del árbol:** `main` `4944fbe5355d66da94290c510e5e0393487f2918`, 2026-11-03.  
**Origen:** árbol GitHub recursivo + código real + migraciones + CI; no el Space ni expedientes reales.  
**Regla:** `MAIN` significa rastreado en Git, **no** desplegado ni verificado E2E. El único comportamiento vigente se determina con el código, no con requerimientos históricos. La validación estática del harness falla al incorporarse nuevos módulos, pruebas, documentos, migraciones o workflows sin incluirlos aquí.

## Cobertura de archivos de aplicación

Hay **35 artefactos** de aplicación en `main` (app + módulos Python + prompts). Estado **runtime** implica que se incluye en el deployment de Hugging Face o que es dependencia de la ruta principal. **No desplegado** implica soporte legado/experimental todavía versionado, no requisito del producto activo.

| Archivo | Estado | Funcionalidad / responsabilidad real | Contratos o advertencias |
|---|---|---|---|
| `app.py` | runtime | Gradio 6: 4 módulos, rutas /privacy, eventos InBody, FitNotes, chat y dashboard | `tests/test_combined_space.py`, `tests/test_sidebar_navigation.py`, `tests/test_inbody_guided_layout.py` |
| `inbody_mvp/__init__.py` | runtime | Paquete Python del MVP | `tests/test_combined_space.py` |
| `inbody_mvp/ai_coach.py` | runtime | Gemini chat: consentimiento, resumen InBody/FitNotes y turnos | `tests/test_ai_coach.py`, `tests/test_coach_conversation.py` |
| `inbody_mvp/app_auth.py` | runtime | Autenticación de la cuenta demo y verificación de contraseña | `tests/test_app_master_login.py` |
| `inbody_mvp/chat_session.py` | runtime | Historial conversacional en sesión, orden y límites | `tests/test_coach_conversation.py` |
| `inbody_mvp/coach_chat_ui.py` | runtime | HTML/CSS del chat responsive, no autentica ni escribe | `tests/test_coach_chat_ui.py` |
| `inbody_mvp/coach_data.py` | runtime | Resolución privada de persona y series FitNotes, sin identificadores en Gemini | `tests/test_coach_auto_data.py` |
| `inbody_mvp/demo_storage.py` | runtime | Escritura demo consentida, aislada y de métricas permitidas | `tests/test_anonymous_demo.py` |
| `inbody_mvp/extractor.py` | runtime/helper legacy | Parser y límites de archivos; OCR determinista heredado; Gemini lo importa para límites | `tests/test_inbody_mvp.py`, `tests/test_ocr_runtime.py` |
| `inbody_mvp/fitness_evidence.py` | no desplegado | Selector de bibliografía local no enlazado automáticamente al chat | sin contrato E2E en main |
| `inbody_mvp/gemini_review.py` | runtime | Gemini Flash, JSON estructurado, revisión, auditar/guardar en Neon, duplicados | `tests/test_gemini_measurement_audit.py`, `tests/test_inbody_one_click_review.py` |
| `inbody_mvp/inbody_flow.py` | runtime | Barra fija 4 pasos Cargar/Extraer/Revisar/Guardar y navegación | `tests/test_inbody_flow.py` |
| `inbody_mvp/language.py` | runtime/helper legacy | Detección idioma ES/EN para utilidades heredadas | `tests/test_language_storage.py` |
| `inbody_mvp/layouts.py` | runtime/helper legacy | OCR espacial InBody 580, tokens y encabezado multicolumna | `tests/test_header_spatial_timestamp.py`, `tests/test_inbody_layouts.py` |
| `inbody_mvp/layouts_es.py` | runtime/helper legacy | Layout español y extracción regional, no UI principal | `tests/test_layout_spanish.py` |
| `inbody_mvp/login_view.py` | runtime | Texto de ayuda para login protegido | `tests/test_login_view.py` |
| `inbody_mvp/navigation.py` | runtime | Sidebar responsive de 4 módulos y estilos | `tests/test_sidebar_navigation.py` |
| `inbody_mvp/oauth_ui.py` | runtime | URLs OAuth standalone validadas para HF Space | `tests/test_oauth_standalone.py` |
| `inbody_mvp/prelogin_consent.py` | runtime | /privacy: 3 permisos, cookie firmada y middleware | `tests/test_prelogin_privacy.py`, `tests/test_session_consent.py` |
| `inbody_mvp/progress_dashboard.py` | runtime | Tendencias InBody Plotly, score, fase angular y segmentación | `tests/test_progress_dashboard.py` |
| `inbody_mvp/project_overview.py` | runtime | Portada Proyecto y arquitectura | `tests/test_sidebar_navigation.py` |
| `inbody_mvp/prompt_loader.py` | runtime | Carga desde allowlist de dos archivos prompt | `tests/test_coach_conversation.py` |
| `inbody_mvp/prompts/fitness_coach.md` | runtime asset | Instrucciones Gemini del coach con límites de interpretación | `tests/test_ai_coach.py` |
| `inbody_mvp/prompts/inbody_extraction.md` | runtime asset | Instrucciones Gemini de extracción del examen presente | `tests/test_gemini_api_contract.py` |
| `inbody_mvp/public_dashboard.py` | runtime | Agregados públicos con controles independientes de publicación | `tests/test_public_dashboard.py`, `tests/test_public_person_series.py` |
| `inbody_mvp/review.py` | runtime/helper legacy | Modelo fila y exportador CSV histórico, NO UI de exportar activa | `tests/test_review.py` |
| `inbody_mvp/section_ai.py` | runtime/optional | Detección visual/layout opcional para ruta antigua; import transitivo | `tests/test_ai_section_ocr.py` |
| `inbody_mvp/section_review.py` | no desplegado | Propuesta/revisión manual de secciones OCR fuera del flujo actual | `tests/test_section_review.py` |
| `inbody_mvp/spatial_rules.py` | no desplegado | Asociación por geometría para OCR experimental | `tests/test_spatial_rules.py` |
| `inbody_mvp/storage.py` | runtime | Canonical InBody: identidad, acceso privado, Neon, esquema confirmado | `tests/test_neon_canonical_storage.py`, `tests/test_inbody_person_alias.py` |
| `inbody_mvp/training_hub.py` | runtime | FitNotes CSV → validación, sets por owner_key, duplicados, importación | `tests/test_training_hub.py`, `tests/test_training_ui_contract.py` |
| `inbody_mvp/upload_preflight.py` | runtime | Consulta hash/nombre para evitar gastar tokens en duplicados | `tests/test_inbody_preflight.py` |
| `inbody_mvp/visual_debug.py` | no desplegado | Overlay/debug de OCR por página; no parte de la UI principal | `tests/test_visual_debug.py` |
| `inbody_mvp/visual_editor.py` | no desplegado | Carga de regiones para editor visual experimental | `tests/test_visual_editor.py` |
| `inbody_mvp/visual_editor_ui.py` | no desplegado | UI estática/editor de secciones experimental | `tests/test_visual_editor.py` |

## Rutas, comportamiento y seguridad verificados en app.py

| Área | Contrato vigente MAIN | Evidencia |
|---|---|---|
| Navegación | Sidebar vertical con Proyecto, Extractor de InBody, Captador FitNotes y Chat; proyecto inicial | `tests/test_sidebar_navigation.py` |
| Consentimientos y rutas HTTP | `/privacy` GET, `/privacy/consent` POST, `/privacy/verify` GET, antes de login; consentimientos independientes para IA de extracción, escritura y coach | `tests/test_prelogin_privacy.py` |
| InBody | cargar archivo, consultar duplicado, seleccionar Gemini, extraer, revisar original junto a tabla, editar valor/comentario, marcar `reviewed`, guardar una vez a Neon | `tests/test_inbody_guided_layout.py`, `tests/test_inbody_one_click_review.py` |
| Progreso | exactamente **Cargar → Extraer → Revisar → Guardar**, barra fija responsive; reset al guardar correctamente | `tests/test_inbody_flow.py` |
| Persistencia | valores originales y finales auditables; signos/decimales, duplicados por identidad/fecha/variable, overwrite explícito, transacción con permiso DB separado | `tests/test_gemini_measurement_audit.py` |
| Dashboard | reportes privados InBody y vista pública separada; Plotly, tendencias, InBody Score, ángulo de fase y segmentación | `tests/test_progress_dashboard.py`, `tests/test_public_person_series.py` |
| FitNotes | importación CSV, vista previa, series, datos negativos, selección de owner, deduplicación, escritura Neon, consulta recientes | `tests/test_training_hub.py` |
| Chat Gemini | mensajes secuenciales en sesión, modelo propio, prompts independientes, InBody y FitNotes privados; `COACH_PERSON_ID` Secret privado o identidad única, límites de contexto, permiso coach | `tests/test_coach_auto_data.py`, `tests/test_coach_conversation.py` |
| Seguridad | cookie previa firmada, login/OAuth según operación, autorización de DB en servidor, alias privado, separación publicación/escritura | `tests/test_session_consent.py`, `tests/test_anonymous_demo.py` |

## Esquema, migraciones y SQL versionados en `main`

- `db/migrations/002_public_aggregate_dashboard.sql`
- `db/migrations/003_public_pseudonymous_series.sql`
- `db/migrations/004_anonymous_consented_demo.sql`
- `db/schema.sql`
- `migrations/004_gemini_measurement_audit.sql`
- `migrations/005_consent_only_audit_writer.sql`
- `migrations/006_app_master_demo_account.sql`
- `migrations/007_idempotent_audit_save.sql`
- `migrations/008_fitnotes_training_hub.sql`
- `sql/20261101_canonical_measurements.sql`

**No confundir** `db/schema.sql` ni `db/migrations/002–004` con las migraciones posteriores `migrations/004–008`. Se conservan rutas históricas. Confirmar siempre permisos y orden de aplicación contra Neon. Los SQL de `sql/` son scripts auxiliares de canonización, no un job automático. El SQL 009 de metadatos se añadió en el PR #84; **se aplicó a `health_journey/main` en Neon**, pero el fichero y lector de la app aún están pendientes de fusionar en GitHub. Ver estado específico del PR.

## CI, despliegue y documentación auxiliar

**GitHub Actions** (3):

- `.github/workflows/deploy-huggingface.yml`
- `.github/workflows/test-inbody.yml`
- `.github/workflows/validar-harness.yml`

**Documentos de soporte** (17):

- `docs/ai-coach.md`
- `docs/auditoria-tecnica-2026-10-31.md`
- `docs/dashboard-publico.md`
- `docs/demo-anonima-consentimiento.md`
- `docs/despliegue-hugging-face.md`
- `docs/fitness-chat-inline-model-selector.md`
- `docs/gemini-measurement-audit.md`
- `docs/hito-semana-2.md`
- `docs/hugging-face-variables-y-secrets.md`
- `docs/inbody-layouts.md`
- `docs/inbody-row-review-actions.md`
- `docs/inbody-upload-preflight.md`
- `docs/indice_actual.md`
- `docs/neon-postgres.md`
- `docs/ocr-secciones-ia.md`
- `docs/public-person-series.md`
- `docs/training-hub.md`

**Raíz no funcional y ejecución local** (10):

- `.env.example`
- `.gitattributes`
- `.gitignore`
- `AGENTS.md`
- `README.md`
- `especificacion.md`
- `requirements-ai.txt`
- `requirements.txt`
- `run_local.sh`
- `run_local_ai.sh`

**Harness de reconstrucción:** `harness/README.md`, `harness/00_estado_vigente_y_trazabilidad.md`, `harness/01_producto_y_alcance.md`, `harness/02_arquitectura_y_flujos.md`, `harness/03_modelo_de_datos_y_csv.md`, `harness/04_extraccion_y_normalizacion.md`, `harness/05_interfaz_y_dashboard.md`, `harness/06_seguridad_y_privacidad.md`, `harness/07_reconstruccion_y_operacion.md`, `harness/08_pruebas_y_criterios.md`, `harness/09_estado_y_decisiones.md`, `harness/10_continuidad_noviembre_2026.md`, `harness/PROMPT_AGENTE.md`, `harness/validar_reconstruccion.py`, y este inventario.

## Inventario total de pruebas

`main` almacena **55 archivos de tests**. No se debe inferir que GitHub Actions ejecuta automáticamente todos: `.github/workflows/test-inbody.yml` declara actualmente una lista explícita, corregida en la propuesta de harness. Tampoco significa test E2E en HF/Neon.

- `tests/test_ai_coach.py`
- `tests/test_ai_section_ocr.py`
- `tests/test_anonymous_demo.py`
- `tests/test_anonymous_demo_callback.py`
- `tests/test_app_master_login.py`
- `tests/test_app_ui_contract.py`
- `tests/test_capture_section_edits.py`
- `tests/test_coach_auto_data.py`
- `tests/test_coach_chat_ui.py`
- `tests/test_coach_conversation.py`
- `tests/test_combined_space.py`
- `tests/test_consent_only_audit.py`
- `tests/test_dashboard_popup_contract.py`
- `tests/test_exam_timestamp.py`
- `tests/test_gemini_api_contract.py`
- `tests/test_gemini_consent.py`
- `tests/test_gemini_failover.py`
- `tests/test_gemini_free_models.py`
- `tests/test_gemini_measurement_audit.py`
- `tests/test_gemini_model_availability.py`
- `tests/test_header_roi_dotted_date.py`
- `tests/test_header_spatial_timestamp.py`
- `tests/test_hf_deploy_contract.py`
- `tests/test_inbody_document_preview.py`
- `tests/test_inbody_flow.py`
- `tests/test_inbody_guided_layout.py`
- `tests/test_inbody_header.py`
- `tests/test_inbody_layouts.py`
- `tests/test_inbody_mvp.py`
- `tests/test_inbody_one_click_review.py`
- `tests/test_inbody_person_alias.py`
- `tests/test_inbody_preflight.py`
- `tests/test_inbody_row_actions.py`
- `tests/test_language_storage.py`
- `tests/test_layout_spanish.py`
- `tests/test_login_view.py`
- `tests/test_measurement_review_schema.py`
- `tests/test_neon_canonical_storage.py`
- `tests/test_oauth_standalone.py`
- `tests/test_ocr_runtime.py`
- `tests/test_phase_angle_measurement.py`
- `tests/test_prelogin_privacy.py`
- `tests/test_progress_dashboard.py`
- `tests/test_public_dashboard.py`
- `tests/test_public_person_series.py`
- `tests/test_review.py`
- `tests/test_section_review.py`
- `tests/test_session_consent.py`
- `tests/test_sidebar_navigation.py`
- `tests/test_single_section_viewer.py`
- `tests/test_spatial_rules.py`
- `tests/test_training_hub.py`
- `tests/test_training_ui_contract.py`
- `tests/test_visual_debug.py`
- `tests/test_visual_editor.py`

## Nuevos artefactos del PR #84: pendientes de `main`

- `migrations/009_ai_semantic_metadata.sql`: catálogos de significado InBody/FitNotes, alias, campos y PostgreSQL `COMMENT ON`. La migración ya se aplicó y verificó contra Neon `health_journey/main`, no presupone que la app actual la lea.
- `inbody_mvp/semantic_metadata.py`: consulta acotada de definiciones, añadida a `load_coach_context` en el PR; **no existe aún en `main`**.
- `tests/test_semantic_metadata.py`: prueba sintética de reglas de glosario y privacidad, pendiente de merge.
- `harness/11_cobertura_codigo_main.md` + verificación de cobertura e índice de documentación actualizados en este PR.

## Riesgos y deuda registrada (sin confundir con funcionalidades)

1. **P0 antes de uso multiusuario:** el acceso InBody basado en identidad privada de una persona no es aislamiento multiusuario completo. No confundir `owner_key` de FitNotes con controles por propietario del examen en Neon. Requiere diseño y pruebas de acceso por persona.
2. **E2E pendiente:** CI y DDL aplicados no validan HF Space, credenciales, Gemini real, navegadores móviles, privacidad ni uso contra exámenes reales.
3. **`.venv/` aparece rastreado en `main`** con **15687 entradas** aunque `.gitignore` lo excluye ahora. Es deuda de higiene y tamaño del repo; **no inspeccionar ni publicar contenido del entorno** como parte del harness. La limpieza requerirá un cambio independiente cuidadosamente revisado.
4. Historial CSV de siete columnas, EasyOCR/PaddleOCR, editor visual y técnicas espaciales están versionados como legado/experimental pero **no son funcionalidades expuestas por la UI activa**. No convertirlos en requisitos obligatorios por aparecer en docs históricas.
5. El catálogo InBody de Neon cubre **35 conceptos, 47 alias y 24 campos documentados** (verificación en Neon el 2026-11-03); sus definiciones son descriptivas, no diagnóstico ni reemplazo de revisión humana.

## Regla de aceptación de cobertura

`python harness/validar_reconstruccion.py` debe:
- localizar cada artefacto `app.py`, `inbody_mvp/**`, `tests/test_*.py`, `docs/*.md`, migración SQL y workflow de GitHub con un enlace literal en este inventario;
- comprobar que el flujo InBody tiene **4 pasos**, solo **Guardar mediciones**, sin retorno a una validación separada;
- rechazar que se reintroduzca como requisito vigente la extracción OCR/CSV histórica o la referencia a PR #72 abierto;
- comprobar permisos separados y archivos de prompt/deploy, y tratar CI como **estático**, no E2E.

El inventario completo impide *ficheros de funcionalidades no documentadas*, pero no prueba semánticamente cada rama de cada función ni garantiza cobertura de ejecución al 100 %. El **código de `main` prevalece** sobre texto antiguo. Actualizar este documento, la matriz de criterios y los tests de una funcionalidad en el **mismo PR** que introduzca su código.
