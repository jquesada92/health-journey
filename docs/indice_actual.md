> **Actualización de consolidación (2026-11-03):** este documento conserva la fotografía de la auditoría original realizada sobre `main` (commit 5f8ea83). Los PR #71, #72, #74 y #75 ya se fusionaron posteriormente. El PR consolidado actual integra la auditoría de #73, las correcciones en línea de #76 y la verificación de duplicados antes de Gemini. Las descripciones de PR pendientes de fusión incluidas en secciones históricas deben interpretarse respecto a la fecha de aquella auditoría. El código de la rama consolidada y sus pruebas constituyen la referencia funcional del cambio; el Space aún requiere validación E2E.\n\n# Índice de documentación y estado de funcionalidades · Health Journey

**Corte de auditoría:** 2026-11-03 UTC, `main` `5f8ea83a5041`.
Leer primero [harness/00 — Estado vigente y trazabilidad](../harness/00_estado_vigente_y_trazabilidad.md).
La existencia de un documento no demuestra que su funcionalidad esté
activa, desplegada o validada E2E. Los históricos no deben usarse como
pasos operativos sin contrastar código y permisos.

| Archivo | Uso actual | Estado y advertencia |
| --- | --- | --- |
| [README raíz](../README.md) | Portada y configuración Hugging Face | MAIN; textos históricos internos pueden describir fases antiguas |
| [AGENTS.md](../AGENTS.md) | Guardrails para agentes y continuidad | Vigencia subordinada al código y al harness 00 |
| [ai-coach.md](ai-coach.md) | Asistente fitness, comparabilidad y privacidad | MAIN con limitaciones del chat; conversación multiturno y prompts por archivo **PR #72 pendiente** |
| [training-hub.md](training-hub.md) | FitNotes CSV → Neon, series por usuario, idempotencia | Código en MAIN; no afirmar datos importados ni E2E |
| [gemini-measurement-audit.md](gemini-measurement-audit.md) | Auditoría de mediciones Gemini y revisión | Vigente como contrato; verificar DDL y funciones en entorno |
| [neon-postgres.md](neon-postgres.md) | Esquema, conexión y notas OAuth | Contiene procedimientos históricos CSV/OCR; contrastar con migraciones 004–008 |
| [despliegue-hugging-face.md](despliegue-hugging-face.md) | Flujo Actions → Space, Secrets y rollback | Vigente parcialmente; no equiparar sync verde a E2E |
| [hugging-face-variables-y-secrets.md](hugging-face-variables-y-secrets.md) | Referencia de configuración | Comprobar variable por variable en código antes de editar entorno |
| [dashboard-publico.md](dashboard-publico.md) | API/dashboard público opcional | Compatibilidad histórica; **no** se publica auditoría privada InBody por guardar |
| [public-person-series.md](public-person-series.md) | Series seudónimas y publicación | Modo especial/legacy; no inferir aislamiento privado multitenant |
| [demo-anonima-consentimiento.md](demo-anonima-consentimiento.md) | Demo y consentimiento distinto de almacenamiento | Modo condicionado por configuración, no flujo principal |
| [inbody-layouts.md](inbody-layouts.md) | Reglas de plantillas espaciales | Legado/soporte de tests; la captura UI principal usa Gemini |
| [ocr-secciones-ia.md](ocr-secciones-ia.md) | Investigación de secciones y evaluación OCR | Investigación/histórico, no flujo UI operativo |
| [auditoria-tecnica-2026-10-31.md](auditoria-tecnica-2026-10-31.md) | Corte histórico de auditoría | No usar como estado vigente posterior a 2026-11-03 |
| [hito-semana-2.md](hito-semana-2.md) | Entrega académica/hitos previos | Documento histórico, no contrato de arquitectura actual |

## Requisitos y criterios vigentes

La trazabilidad funcional principal está en
[harness/00](../harness/00_estado_vigente_y_trazabilidad.md) (F-01…F-15 y
AC-V-01…AC-V-12). Los criterios **CA-01…CA-36** y **CS-01…CS-10**
de [harness/08](../harness/08_pruebas_y_criterios.md)
continúan disponibles como requisitos de visión/compatibilidad;
cada uno debe revisarse antes de declararse entregado.

## Tecnologías y responsabilidades

- **Python 3.12** en CI; `Gradio 6` y CSS para interfaz y estados.
- **Google Gemini Flash** por `google-genai`: extracción e interacción fitness;
  cada módulo mantiene su selector independiente.
- **Neon PostgreSQL** con `SQLAlchemy` y `psycopg`: auditoría y series;
  `alembic` instalado, DDL real en `db/schema.sql` y `migrations/`.
- **Pydantic**, `Decimal`, `Pandas`, `Plotly`, `PyMuPDF`, `Pillow`:
  contratos, precisión, visualización y preparación PDF/imagen.
- **Hugging Face Spaces** con `spaces` por compatibilidad ZeroGPU y
  **GitHub Actions** para CI y sincronización. Gemini no precisa GPU local.
- **EasyOCR/PaddleOCR/editores espaciales**: código histórico fuera del
  runtime distribuido principal, con tests heredados.
- **Google Gemini prompts independientes + turnos reales**: implementado
  en PR #72 abierto, **todavía no en `main`** en este corte.
- **RAG científico**: no reivindicar integración de evidencia recuperada
  hasta validarla expresamente; `fitness_evidence.py` existe en `main`
  pero no equivale por sí solo a un servicio de recuperación bibliográfica.

## Actualizaciones de documentación obligatorias en cada PR

1. Identificar commit base, rama/PR, pruebas ejecutadas y si se comprobó Space.
2. Actualizar funcionalidades F, criterios AC-V y tests (sin borrar legado).
3. Actualizar tecnologías/dependencias, migraciones, secretos o permisos
   **solo si cambiaron realmente** y sin revelar valores secretos.
4. Comprobar rutas del harness, tests y lista de archivos permitidos de deploy.
5. Añadir evidencia visual móvil y E2E únicamente cuando se ejecutó;
   no convertir pruebas sintéticas en aceptación clínica/operativa.
6. Mantener separadas las acciones aprobadas, las propuestas y la
   documentación histórica (fecha y PR).
