> **Confirmación única de correcciones (2026-11-03, PR propuesto):**
> **Guardar cambios** toma directamente los valores editados en la tabla,
> reconcilia eliminaciones nativas y valida comentarios, unidades y valores.
> Solo si la validación finaliza correctamente marca automáticamente
> `reviewed` para todas las filas conservadas y avanza. No hay que marcar
> cada fila por separado; las lecturas originales siguen inmutables.
> Al extraer, la elección de consentimiento firmada en servidor prevalece
> sobre el estado de Gradio para evitar falsos avisos por inicialización
> tardía; sin consentimiento real, el envío a Gemini sigue bloqueado.
> No cambia el consentimiento independiente de escritura en Neon.
> Regresión: `tests/test_inbody_one_click_review.py`.

> **Visor y consentimiento (2026-11-03, PR #80, verificación pendiente):**
> la vista paralela se activa solamente después de extracción válida;
> PDF/imágenes a la derecha en una galería vertical, tabla a la
> izquierda, y apilados en móvil. `privacy/verify` verifica la sesión
> firmada después del formulario antes de entrar a Gradio y proporciona
> una explicación si el navegador no conserva la cookie, sin relajar
> CSRF ni el consentimiento obligatorio. Se mantiene el bloqueo
> de duplicados previo a Gemini. Contratos:
> `tests/test_inbody_guided_layout.py`,
> `tests/test_inbody_document_preview.py`,
> `tests/test_prelogin_privacy.py`. CI no demuestra visualización
> real en Hugging Face.

> **Revisión paralela InBody (2026-11-03, PR propuesto):** tras extraer,
> la tabla de mediciones aparece a la izquierda del visor original
> PDF/imagen en escritorio, sin acordeón. El visor muestra páginas,
> permite pantalla completa y se mantiene en el flujo de validación;
> en móvil la disposición se apila. Los controles de edición,
> `was_corrected`, eliminación nativa, revisión humana, consentimiento
> y persistencia no cambian. Se incluye corrección del input
> `gemini_upload_preflight` en la llamada a `extract_with_popup`.
> Pruebas: `test_inbody_guided_layout.py`,
> `test_inbody_document_preview.py`, `test_gemini_consent.py`.
> Requiere CI y validación manual en Space.

> **Revisión y filas nativas (PR #79, 2026-11-03):** la tabla InBody
> permite corregir valores y eliminar filas directamente con las
> herramientas nativas de Gradio 6. Ya no se selecciona una fila para
> pulsar un botón externo. Cada edición actualiza `was_corrected`
> automáticamente y cada borrado reconcilia la tabla con sus orígenes
> auditables; se rechazan fuentes indistinguibles o manipuladas. El
> botón **Guardar cambios** verifica revisión y comentarios, pero no
> persiste en Neon. Se conservan los avisos de error unificados del
> mismo PR. Contratos: `tests/test_inbody_row_actions.py`,
> `tests/test_dashboard_popup_contract.py`,
> `tests/test_inbody_flow.py`. Falta validación visual en el Space.

> **Ajuste de UX propuesto (2026-11-03, aún no desplegado):** retirar las
> marcas/recuadros de validación por componente de Gradio 6, conservar
> un único popup de error (`gr.Warning`) o el mensaje contextual del
> archivo, y mantener oculto el estado interno de validación. La
> comprobación de mediciones, `original_value`, consentimiento y
> deduplicación continúa en backend. Contratos en
> `tests/test_dashboard_popup_contract.py`. Requiere CI y prueba en Space.

> **Actualización de consolidación (2026-11-03):** este documento conserva la fotografía de la auditoría original realizada sobre `main` (commit 5f8ea83). Los PR #71, #72, #74 y #75 ya se fusionaron posteriormente. El PR consolidado actual integra la auditoría de #73, las correcciones en línea de #76 y la verificación de duplicados antes de Gemini. Las descripciones de PR pendientes de fusión incluidas en secciones históricas deben interpretarse respecto a la fecha de aquella auditoría. El código de la rama consolidada y sus pruebas constituyen la referencia funcional del cambio; el Space aún requiere validación E2E.\n\n# 00 — Estado vigente, capacidades, requisitos y trazabilidad de Health Journey

**Auditoría documental:** 2026-11-03 (UTC). **Base contrastada:** `main`
`5f8ea83a504182211f090ff45e1d0e5fd9434927`, árbol de archivos
GitHub, `app.py`, módulos, requisitos, migraciones, tests y workflows.
**No es una prueba de operaciones reales ni de datos de usuarios**:
no se abrieron expedientes, se ejecutó SQL contra Neon ni se verificó
interactivamente el Space. Los workflows de sincronización pueden
terminar en verde sin demostrar que el navegador o el proveedor IA funcionen.

Este documento es el **inventario operativo prioritario**. Los requisitos
anteriores conservados en `01–10` documentan alcance histórico o visión
futura cuando contradicen el código actual. El código y las migraciones
son fuente de verdad para comportamiento y estructura; el estado en un
servidor externo se debe comprobar por separado. No inferir que una
migración está aplicada porque su fichero exista.

## 1. Estado por categoría

Leyenda: **MAIN** = presente en código `main` con pruebas sintéticas;
**PR** = existe en propuesta no fusionada; **LEGACY** = código/contrato
histórico sin exposición principal; **PENDIENTE** = no verificado o no
implementado en el flujo de la aplicación. MAIN no equivale a E2E.

| ID | Funcionalidad / requisito | Estado | Implementación | Test o evidencia estática |
| --- | --- | --- | --- | --- |
| F-01 | Menú vertical exactamente Proyecto, Extractor de InBody, Captador de logs de entrenamiento, Chat fitness; Proyecto inicial; responsive | MAIN | `app.py`, `navigation.py`, `project_overview.py` | `test_sidebar_navigation.py` |
| F-02 | Carga PDF/JPG/JPEG/PNG, vista previa, consulta de nombre previamente procesado | MAIN | `app.py`, `gemini_review.py`, `extractor.py` | `test_inbody_document_preview.py`, `test_consent_only_audit.py` |
| F-03 | Dropdown Gemini del extractor, extracción explícita y JSON tipado; no importar historial dibujado | MAIN | `gemini_review.py` | `test_gemini_api_contract.py`, `test_gemini_consent.py`, `test_gemini_measurement_audit.py` |
| F-04 | Encabezado InBody único, tabla editable, revisión humana, valores textuales con decimales exactos; fase angular/impedancia como mediciones | MAIN | `app.py`, `gemini_review.py` | `test_inbody_header.py`, `test_phase_angle_measurement.py`, `test_gemini_measurement_audit.py` |
| F-05 | Guía fija de 5 pasos Cargar → Extraer → Revisar → Validar → Guardar; navegación tras éxito, no saltar por cada edición | MAIN | `inbody_flow.py`, `app.py` | `test_inbody_flow.py`, `test_inbody_guided_layout.py` |
| F-06 | Auditoría privada en Neon después de revisar; detectar archivo previo y pedir confirmación antes de sobreescribir; reset tras guardar correctamente | MAIN (código) | `gemini_review.py`, `migrations/004–007` | `test_consent_only_audit.py`, `test_inbody_guided_layout.py` |
| F-07 | Plotly de progreso InBody, incluido InBody Score y ángulo de fase, dentro del extractor; no pestaña «Historial» separada | MAIN | `progress_dashboard.py`, `app.py` | `test_progress_dashboard.py`, `test_sidebar_navigation.py` |
| F-08 | FitNotes CSV → validación, vista previa, series por usuario, unidades/negativos, duplicados, sobreescritura explícita y escritura a Neon | MAIN (código) | `training_hub.py`, `migrations/008_fitnotes_training_hub.sql` | `test_training_hub.py`, `test_training_ui_contract.py` |
| F-09 | Consentimientos independientes de extracción Gemini, escritura DB y chat Gemini, desmarcados y preguntados **antes del login** | MAIN | `prelogin_consent.py`, `app.py` (tres `gr.State`) | `test_prelogin_privacy.py`, `test_session_consent.py` |
| F-10 | Gemini Chat privado con selección de modelo **independiente** del extractor, objetivos, restricciones y resúmenes FitNotes/InBody | MAIN (código, comportamiento conversacional limitado) | `ai_coach.py`, `coach_chat_ui.py`, `app.py` | `test_ai_coach.py`, `test_coach_chat_ui.py` |
| F-11 | Mensajes secuenciales estilo WhatsApp, multi-turno real, historial visual independiente del contexto Gemini y prompts en ficheros separados | **PR #72; NO MAIN** | rama `fix/multiturn-gemini-chat-separate-prompts-20261103` | CI del PR: 317 pruebas, 1 aviso; no E2E |
| F-12 | Biblioteca local de referencias de entrenamiento | MAIN **como módulo, sin integración demostrada en chatbot** | `fitness_evidence.py` | No afirmar que el chat recupere citas verificadas |
| F-13 | OCR EasyOCR/PaddleOCR, editor espacial y CSV de siete columnas con dashboard combinado CSV/Neon | LEGACY o propuesta previa | `extractor.py`, `review.py`, módulos espaciales y `db/schema.sql` | Tests heredados; no activarlo de oficio en el Space |
| F-14 | Aislamiento verdadero de datos InBody por propietario en escenario multiusuario | PENDIENTE | lectores InBody aceptan ID indicado; FitNotes sí usa `owner_key` | Revisión de seguridad y pruebas multitenant requeridas |
| F-15 | Validación integral en el Space, navegador móvil, Gemini real y Neon autorizado | PENDIENTE de evidencia E2E | despliegue GitHub Actions y secretos externos | No se certifica mediante pytest o status de workflow |

**Precisión de límites:** la utilidad heredada `extractor.py` usa
15 MiB, 8 páginas y 20 megapíxeles para su flujo antiguo. La
ruta activa `gemini_review._pages` admite hasta **10 páginas** y
consulta `MAX_UPLOAD_BYTES` del extractor: no confundir los dos
límites de páginas. FitNotes: **10 MiB, 100.000 filas** y vista previa
máxima de **60** (`training_hub.py`). El coach acepta periodos de
**30/90/180/365 días** y limita el volumen de contexto compartido.

## 2. Arquitectura y tecnologías reales

```text
Navegador / móvil
  -> Hugging Face Space: Gradio 6 / app.py / sidebar 4 módulos
       -> /privacy (tres opt-in) -> Gradio auth / OAuth según operación
       -> InBody PDF / imagen -> PyMuPDF + Pillow -> Gemini Flash API
          -> validación Pydantic -> revisión humana / Decimal
          -> función SQL de auditoría -> Neon PostgreSQL
          -> Plotly / Pandas: tendencias privadas
       -> FitNotes CSV -> parser Python/Pandas -> validación e idempotencia
          -> transacción SQLAlchemy + psycopg -> Neon PostgreSQL
       -> Asistente -> resúmenes de datos autorizados (no PDF/CSV)
          -> Gemini Flash API -> Gradio Chatbot
GitHub -> Actions (Ruff/compilación/pytest/harness) -> deploy Space
```

**Instalado en `requirements.txt`:** Python 3.12 en CI;
`gradio[oauth]>=6,<7`, `google-genai>=1,<2`, `spaces` (compatibilidad
con infraestructura ZeroGPU; Gemini no se ejecuta como modelo local),
`pydantic` v2, `pydantic-settings`, `python-dotenv`,
`SQLAlchemy` 2, `psycopg` 3, `alembic`, `pandas` 2/3,
`plotly` 6, `PyMuPDF`, `Pillow`, `numpy`, `rapidfuzz`,
`python-dateutil`. **No afirmar que todas las librerías instaladas
son utilizadas por la ruta principal**. Las dependencias de EasyOCR y
PaddleOCR no están en el runtime principal. El usuario elige un modelo
Gemini por módulo; el inventario de modelos gratuitos es una allowlist
y la cuota/coste real depende del proyecto de Google.

**Persistencia:** `db/schema.sql` contiene el esquema original,
`migrations/004_gemini_measurement_audit.sql` auditorías InBody,
`005_consent_only_audit_writer.sql` mínimos permisos/alias,
`006_app_master_demo_account.sql` cuenta de demo,
`007_idempotent_audit_save.sql` guardado y confirmación,
`008_fitnotes_training_hub.sql` series. **Versionar DDL no demuestra
que todas estas migraciones estén aplicadas**. Los historiales y auditorías
privados no se publican solo por conceder permiso de almacenamiento.

**Seguridad:** cookie previa al login firmada y temporal; tres decisiones
independientes y opcionales, recuperación en `gr.State`, chequeo
servidor de `has_consent` y controles de acceso. Se distinguen
persistencia privada y demostración/publicación. No subir reportes
identificables a pruebas públicas. La consulta InBody por ID NO ofrece
aislamiento multitenant robusto; debe bloquearse un lanzamiento
multiusuario real sin row-level ownership, permisos y pruebas.

## 3. Matriz de aceptación operativa

No confundir **CI aprobado** con aceptación E2E. Cada caso necesita
resultado, evidencia (test o acta), SHA y entorno. Las claves `CA-01…36`
y `CS-01…10` del documento 08 se conservan como **criterios de visión
histórica**, no se dan por aprobadas automáticamente.

| Criterio actual | Dado / cuando / entonces | Evidencia y resultado |
| --- | --- | --- |
| AC-V-01 | Al entrar tras login, se abre Proyecto y el sidebar tiene cuatro opciones en el orden especificado, también en móvil | Sintético: `test_sidebar_navigation.py`; **E2E pendiente** |
| AC-V-02 | Antes del login, los tres permisos están sin marcar; operaciones Gemini/Neon rechazan consentimientos ausentes o forjados | `test_prelogin_privacy.py`, `test_session_consent.py`, `test_gemini_consent.py`; E2E pendiente |
| AC-V-03 | InBody extrae solo valores actuales y preserva `8.20`, unidades, fecha, ID y segmento; correcciones exigen revisión | `test_inbody_header.py`, `test_gemini_measurement_audit.py`, `test_inbody_document_preview.py`; fixture real anon. pendiente |
| AC-V-04 | La barra de 5 pasos no se mueve al hacer scroll ni tapa campos; el avance ocurre solo al completar el paso | `test_inbody_flow.py`, `test_inbody_guided_layout.py`; **test visual móvil pendiente** |
| AC-V-05 | Ante fallo de guardado no se pierden datos; al éxito limpia y vuelve a Cargar sin cambiar permisos | `test_inbody_guided_layout.py`, `test_consent_only_audit.py`; DB real pendiente |
| AC-V-06 | FitNotes mantiene orden, decimales, unidad, negativos y series reales; duplicado solicita confirmación | `test_training_hub.py`, `test_training_ui_contract.py`; Neon E2E pendiente |
| AC-V-07 | InBody Plotly compara series compatibles, InBody Score y ángulo de fase con reglas de calidad | `test_progress_dashboard.py`; verificación con varias fechas reales pendiente |
| AC-V-08 | Chat consulta datos autorizados y no envía documento, identificador, CSV o OCR sin permiso, ni inventa comparabilidad | `test_ai_coach.py`; seguridad multiusuario y Gemini real pendientes |
| AC-V-09 | En PR #72: Enviar y Enter producen burbuja inmediata, indicador temporal y respuesta en orden; segunda pregunta retiene contexto | `test_coach_conversation.py` de **PR**, 317 aprobadas; **pendiente de merge/E2E** |
| AC-V-10 | Un prompt distinto controla extractor y chat; se incluyen archivos en deploy y el coach no inventa bibliografía | **PR #72**: `prompt_loader.py`, `prompts/*.md`, test de aislamiento; pendiente en `main` |
| AC-V-11 | Una instancia nueva instala DDL necesario, configura Secrets sin exponerlos, levanta Space y permite guardado/consulta autorizados | **PENDIENTE** de prueba de reconstrucción completa |
| AC-V-12 | Una segunda cuenta no puede consultar, adivinar, modificar ni exportar un ID InBody ajeno | **PENDIENTE** de aislamiento multiusuario; no declarar listo para producción |

## 4. Tests, CI y puertas de calidad

- `.github/workflows/test-inbody.yml`: Ruff `F821`, `compileall`,
  pytest de fixtures **sintéticos**, sin claves Gemini/Neon. Actualmente
  enumera explícitamente módulos de tests; no asumir que ejecuta todos los
  archivos de `tests/`. Actualizarlo al añadir suites nuevas.
- `.github/workflows/validar-harness.yml`: valida la estructura documental y los contratos estáticos mediante `harness/validar_reconstruccion.py`; no accede a servicios externos.
- `harness/validar_reconstruccion.py`: comprueba estructura y los
  36 criterios CA + 10 CS heredados; requiere ampliación de validaciones
  actuales, no certifica instalación ni privacidad E2E.
- `.github/workflows/deploy-huggingface.yml`: despliega `main`
  al Space usando allowlist explícita, variable `HF_SPACE_ID` y secreto
  `HF_TOKEN`; éxito en Actions no prueba funcionalidad visual.
- Evidencia más reciente verificada: CI de **PR #72**: 317 tests
  aprobados, 1 aviso; está abierto y sus cambios de chat/prompts NO
  forman parte de este snapshot de `main`.
- `main` `5f8ea83a5041`: workflow de sincronización HF concluyó
  correctamente en GitHub Actions; funcionamiento real del Space no
  fue inspeccionado durante esta auditoría.

## 5. Riesgos, deuda y decisiones

1. **P0:** aislamiento InBody por dueño (`owner_key` no se aplica a
   todas las consultas InBody): riesgo crítico para multiusuario.
2. **P0:** validar consentimientos, auth, Gemini real, escritura, consulta,
   sobrescritura y reinicio en Space con datos de prueba seguros.
3. **P1:** cerrar y probar PR #72 (prompts, mensajes secuenciales).
4. **P1:** generar evidencia visual móvil de navbar fija y del chat.
5. **P1:** confirmar migraciones realmente aplicadas en Neon y
   mínimos privilegios de roles (sin leer datos personales).
6. **P2:** registrar tiempos de inferencia, costes/cuotas y latencia.
7. **P2:** mantener funcionalidades legacy fuera de requisitos operativos
   hasta aprobar una reintroducción explícita.
8. **P2:** el catálogo `fitness_evidence.py` debe validarse e integrarse
   expresamente antes de decir que el coach está fundamentando respuestas
   con recuperación documental; no confundir un prompt científico con RAG.

## 6. Orden de consulta

1. **Este fichero**: estado y criterios actuales.
2. `harness/README.md`: navegación del harness y reglas de precedencia.
3. `harness/01–08`: dominios y requisitos históricos complementarios;
   leer su nota vigente al comienzo, no tomar textos de octubre como
   funcionalidades ya desplegadas.
4. `harness/09–10`: decisiones y continuidad; conservar fechas y PR.
5. `docs/indice_actual.md`: mapas a docs operativas.
6. `requirements.txt`, `app.py`, `inbody_mvp/`, `migrations/`,
   `tests/`, workflows y PR #72 para resolver discrepancias.

**Regla de documentación:** todo cambio de alcance o función debe actualizar
los criterios AC-V pertinentes, el test asociado, el harness y el inventario
de tecnologías, distinguiendo `main`, PR y E2E verificado.
