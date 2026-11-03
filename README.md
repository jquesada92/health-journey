---
title: Health Journey
emoji: 💪
colorFrom: blue
colorTo: green
sdk: gradio
python_version: "3.12"
app_file: app.py
hf_oauth: true
---

# Health Journey

Health Journey es una aplicación de seguimiento de composición corporal y entrenamientos. Unifica reportes **InBody**, registros **FitNotes** y un asistente conversacional basado en **Gemini**, con interfaz web en **Gradio** y almacenamiento privado en **Neon PostgreSQL**.

**Aplicación:** https://jaqo-health-journey.hf.space/  
**Repositorio:** https://github.com/jquesada92/health-journey  
**Referencia de arquitectura y estado:** [harness/00_estado_vigente_y_trazabilidad.md](harness/00_estado_vigente_y_trazabilidad.md)  
**Documentación técnica:** [docs/indice_actual.md](docs/indice_actual.md)  
**Historial de cambios y notas anteriores:** [docs/history/README-historico-2026-11-03.md](docs/history/README-historico-2026-11-03.md)

> **Referencia documental: 2026-11-03.** La presencia de código o documentación no demuestra que un módulo, una migración o un PR estén desplegados y validados de extremo a extremo. Consultar el estado vigente y los tests antes de operar con datos reales.

## Arquitectura y flujo de datos

```text
Usuario → interfaz Gradio (app.py) / autorización y consentimiento
             │
             ├─ InBody: PDF/imagen → Gemini + prompt de extracción
             │          → JSON/Pydantic → tabla editable + revisión
             │          → escritura autorizada en Neon PostgreSQL
             │
             ├─ FitNotes: CSV → validación Python/Pandas
             │             → series de entrenamiento en Neon
             │
             ├─ Historial: lectura autorizada de Neon → Plotly
             │
             └─ Chat: lectura autorizada InBody + FitNotes
                        → contexto JSON acotado + prompt del coach
                        → Gemini → respuesta en Gradio

GitHub Actions → pruebas y validación documental → despliegue a Hugging Face
```

**Responsabilidades:** Gemini interpreta documentos y genera respuestas; **no accede directamente a PostgreSQL**. Python valida los datos y las respuestas, administra permisos y consentimientos, realiza las consultas SQL y persiste los registros confirmados. El importador FitNotes no envía el archivo CSV a Gemini; las series autorizadas pueden alimentar después el contexto del asistente.

## Estructura del repositorio

| Carpeta o archivo | Función |
| --- | --- |
| [`app.py`](app.py) | Entrada principal de Gradio; pantallas, navegación y callbacks de InBody, FitNotes, Chat y Proyecto. |
| [`inbody_mvp/`](inbody_mvp/) | Código Python de negocio, extracción, revisión, permisos, consultas, visualizaciones y chat. |
| [`inbody_mvp/prompts/`](inbody_mvp/prompts/) | Prompts independientes para extracción de documentos y conversación de fitness. |
| [`tests/`](tests/) | Pruebas unitarias, regresiones y contratos funcionales y de seguridad. |
| [`db/`](db/) | Esquema SQL inicial y migraciones de compatibilidad/etapas anteriores. |
| [`migrations/`](migrations/) | Evoluciones SQL versionadas para auditorías, autorización, FitNotes y metadatos. Verificar cada migración antes de aplicarla. |
| [`sql/`](sql/) | Scripts SQL adicionales relacionados con el modelo de datos. |
| [`docs/`](docs/) | Documentación por funcionalidad, configuración, seguridad y operación. |
| [`docs/history/`](docs/history/) | Archivo de cambios y notas históricas; no usar como especificación vigente. |
| [`harness/`](harness/) | Especificación, arquitectura, requisitos, criterios de aceptación, trazabilidad y validación de reconstrucción. |
| [`.github/workflows/`](.github/workflows/) | CI, verificación documental y sincronización con Hugging Face Spaces. |
| [`AGENTS.md`](AGENTS.md) | Reglas y contexto para agentes de programación que mantienen el proyecto. |
| [`especificacion.md`](especificacion.md) | Especificación funcional de referencia; contrastar con el estado actual del harness. |
| [`requirements.txt`](requirements.txt) | Dependencias principales de ejecución. |
| [`requirements-ai.txt`](requirements-ai.txt) | Dependencias adicionales/experimentales de IA, no necesariamente incluidas en producción. |
| [`.env.example`](.env.example) | Plantilla de variables de entorno sin credenciales. |
| [`run_local.sh`](run_local.sh), [`run_local_ai.sh`](run_local_ai.sh) | Scripts auxiliares de arranque local. |

La carpeta `.venv/` aparece en el árbol de GitHub, pero es un entorno local de Python, **no** un componente del producto ni un paquete para desplegar. Las dependencias de referencia son las declaradas en los archivos `requirements*.txt`.

### Ficheros clave de `inbody_mvp/`

| Fichero | Responsabilidad |
| --- | --- |
| [`gemini_review.py`](inbody_mvp/gemini_review.py) | Extracción InBody con Gemini, estructura de salida, revisión y auditoría de mediciones. |
| [`filename_timestamp.py`](inbody_mvp/filename_timestamp.py) | Interpretación de fechas del reporte y de la marca temporal del nombre del archivo. |
| [`upload_preflight.py`](inbody_mvp/upload_preflight.py) | Verificación previa de archivos, duplicados y condiciones de reprocesamiento. |
| [`inbody_flow.py`](inbody_mvp/inbody_flow.py) | Flujo InBody: **Cargar → Extraer → Revisar → Guardar**. |
| [`review.py`](inbody_mvp/review.py) | Modelos y reglas de revisión; incluye utilidades heredadas de compatibilidad. |
| [`storage.py`](inbody_mvp/storage.py) | Acceso privado a Neon, validación de autorización y persistencia. |
| [`training_hub.py`](inbody_mvp/training_hub.py) | Importación, validación y deduplicación de series FitNotes desde CSV. |
| [`ai_coach.py`](inbody_mvp/ai_coach.py) | Orquestación de las consultas a Gemini para el asistente conversacional. |
| [`coach_data.py`](inbody_mvp/coach_data.py) | Lecturas autorizadas y preparación de contexto InBody/FitNotes para el chat. |
| [`chat_session.py`](inbody_mvp/chat_session.py) | Orden e historial de los mensajes durante la sesión. |
| [`coach_chat_ui.py`](inbody_mvp/coach_chat_ui.py) | Estilos y presentación de la conversación. |
| [`coach_trends.py`](inbody_mvp/coach_trends.py) | Tendencias compactas de composición corporal para el chat. |
| [`progress_dashboard.py`](inbody_mvp/progress_dashboard.py) | Gráficos de evolución y métricas InBody. |
| [`semantic_metadata.py`](inbody_mvp/semantic_metadata.py) | Lectura condicionada de definiciones semánticas, cuando su integración está habilitada. |
| [`prompt_loader.py`](inbody_mvp/prompt_loader.py) | Carga de los dos prompts autorizados desde archivos versionados. |
| [`prelogin_consent.py`](inbody_mvp/prelogin_consent.py), [`app_auth.py`](inbody_mvp/app_auth.py), [`oauth_ui.py`](inbody_mvp/oauth_ui.py) | Consentimiento, autenticación y acceso a operaciones privadas. |
| [`navigation.py`](inbody_mvp/navigation.py), [`project_overview.py`](inbody_mvp/project_overview.py) | Navegación responsive e información de proyecto. |
| [`module1_deliverable.py`](inbody_mvp/module1_deliverable.py) | Generación del documento académico desde la interfaz Proyecto. |

Los ficheros `layouts*.py`, `spatial_rules.py`, `section_*.py`, `visual_editor*.py` y `visual_debug.py` incluyen implementaciones auxiliares, heredadas o experimentales de OCR y análisis espacial. **No** sustituyen el flujo principal de extracción mediante Gemini.

### Prompts separados por funcionalidad

- [`inbody_mvp/prompts/inbody_extraction.md`](inbody_mvp/prompts/inbody_extraction.md): lectura del examen actual, identificación de secciones, valores y unidades, y salida JSON estructurada.
- [`inbody_mvp/prompts/fitness_coach.md`](inbody_mvp/prompts/fitness_coach.md): asistente conversacional que trabaja con datos autorizados de InBody/FitNotes y reconoce incertidumbre y límites de la evidencia.

`AGENTS.md` tiene otro propósito: proporciona instrucciones **a los agentes que desarrollan el software**, no al modelo Gemini que atiende las consultas de la aplicación.

## Documentación, pruebas y despliegue

- **Estado funcional y limitaciones:** [harness/00](harness/00_estado_vigente_y_trazabilidad.md), [docs/indice_actual.md](docs/indice_actual.md).
- **Arquitectura, seguridad y criterios:** [harness/02](harness/02_arquitectura_y_flujos.md), [harness/06](harness/06_seguridad_y_privacidad.md), [harness/08](harness/08_pruebas_y_criterios.md).
- **Cobertura de archivos y tests:** [harness/11](harness/11_cobertura_codigo_main.md) y [tests/](tests/).
- **Persistencia:** [docs/neon-postgres.md](docs/neon-postgres.md) y [migrations/](migrations/).
- **Entrenamientos:** [docs/training-hub.md](docs/training-hub.md).
- **Asistente:** [docs/ai-coach.md](docs/ai-coach.md).
- **Despliegue:** [docs/despliegue-hugging-face.md](docs/despliegue-hugging-face.md) y [`.github/workflows/deploy-huggingface.yml`](.github/workflows/deploy-huggingface.yml).
- **Historial documental:** [docs/history/README-historico-2026-11-03.md](docs/history/README-historico-2026-11-03.md), conservado íntegro desde el antiguo README.

Para ejecutar las pruebas en un entorno preparado con las dependencias correspondientes:

```bash
python -m pytest -q
python harness/validar_reconstruccion.py
```

Estas comprobaciones **no sustituyen** la validación en navegador del Space ni la verificación de permisos y datos reales en Neon. Los secretos de Gemini, la base de datos y Hugging Face deben configurarse mediante variables privadas de entorno o secretos del servicio, nunca en Git.

