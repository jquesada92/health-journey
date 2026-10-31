# 02 — Arquitectura técnica y flujos de datos

## 1. Stack obligatorio del MVP

- **Frontend/servidor web:** Gradio `Blocks`, pestañas y componentes `File`, `Dataframe`, `Plot` y controles de sesión.
- **Visualizaciones:** Plotly (líneas interactivas); Pandas para preparación.
- **Extracción:** PyMuPDF para texto nativo PDF, EasyOCR para imágenes y páginas escaneadas; OCR con coordenadas `detail=1`. ZeroGPU según elegibilidad del Space.
- **Modelo/validación:** Python 3.12 como referencia en CI, Pydantic v2.
- **BD:** PostgreSQL 17 en Neon, acceso con SQLAlchemy 2 y psycopg 3. Alembic para evoluciones controladas.
- **Hosting:** Hugging Face Spaces `sdk: gradio`, `app_file: app.py`. GitHub Actions sincroniza los archivos necesarios.
- **Autenticación:** OAuth de Hugging Face; autorización de lado servidor y privilegios mínimos de BD.
- **Pruebas:** pytest con fixtures sintéticos; no depende de una base real ni de pesos OCR descargados para pruebas unitarias.

**No utilizar Dash, Flask o React como interfaz del MVP.** No sustituir Gradio por Docker sin justificación y aprobación.

## 2. Diagrama lógico

```mermaid
flowchart TD
  A[Reporte PDF JPG PNG] --> B[Gradio app.py]
  B --> C[Validación de archivo]
  C --> D[PDF texto o EasyOCR con posiciones]
  D --> E[Detector de plantilla e idioma]
  E --> F[Normalizador Pydantic]
  F --> G[Tabla editable y revisión humana]
  G --> H[Exportar CSV con hash y UTC]
  G -->|Confirmación autenticada| I[Servicio de persistencia]
  I --> J[(Neon PostgreSQL)]
  J --> K[Adaptador de historial Neon]
  H --> L[Importador de múltiples CSV]
  L --> M[Modelo de visualización común]
  K --> M
  M --> N[Gradio Plotly Dashboard]
```

**Aclaración:** la dirección de conexión SQL es del backend de Gradio hacia Neon, tanto para lectura como escritura. Neon no necesita llamar a Hugging Face. El CSV es una alternativa autónoma, no un reemplazo de la BD.

## 3. Mapeo a archivos existentes

| Archivo actual | Responsabilidad |
| --- | --- |
| `app.py` | Punto de entrada, UI Gradio, eventos y control de acceso de operaciones |
| `inbody_mvp/extractor.py` | Validar archivo, extraer PDF/imagen, producir candidatos Pydantic |
| `inbody_mvp/layouts.py` | Detector/parser espacial para plantilla conocida InBody 580 |
| `inbody_mvp/layouts_es.py` | Parser de plantilla española con siluetas y frecuencias |
| `inbody_mvp/language.py` | Determinar idioma ES/EN/UNKNOWN conservadoramente |
| `inbody_mvp/review.py` | Tabla editable, validación y contrato CSV v1 |
| `inbody_mvp/storage.py` | Autorización, escritura transaccional, lectura Neon |
| `db/schema.sql` | DDL versionado del esquema inicial |
| `tests/` | Casos unitarios sintéticos y regresiones |
| `.github/workflows/deploy-huggingface.yml` | Sincronización del Space |
| `.github/workflows/test-inbody.yml` | Pruebas en PR |

**Ampliaciones recomendadas:** `inbody_mvp/dashboard.py` para adaptadores Neon/CSV y gráficos; `inbody_mvp/exports.py` para nombres y contratos de archivo. Estas rutas son propuesta, no parte de la implementación verificada de `main` al redactar.

## 4. Flujo de carga y extracción

1. Subida Gradio (temporal) → comprobación firma, límites y tipo.
2. PDF de texto: PyMuPDF antes de OCR; PDF escaneado/imagen: EasyOCR. Conservar cajas y confianza por bloque donde estén disponibles.
3. Selección de parser según evidencia del modelo/plantilla. Si la plantilla no encaja, parser genérico conservador.
4. Detección de idioma del reporte por encabezados. Si evidencia insuficiente, `UNKNOWN`.
5. Modelo candidato: metadatos, lista de medidas, advertencias y procedencia por página.
6. Tabla editable con validaciones: el usuario confirma valores y metadatos o los deja sin resolver.
7. Exportación CSV independiente o guardado autorizado en Neon.
8. No borrar una evaluación existente automáticamente al reimportar.

## 5. Flujo del dashboard y separación de responsabilidades

- **Ruta Neon:** OAuth válido → autorización → consulta SQL parametrizada y acotada → adaptador de datos → filtros → Plotly.
- **Ruta CSV:** archivos CSV seleccionados → validación de contrato/UTF-8/tamaño → unión de filas → descarte de duplicados idénticos → filtros → Plotly. **Prohibido** escribir a Neon en esta ruta.
- Mantener `source_type`, etiqueta original, modelo, frecuencia y origen cuando existan. El CSV v1 tiene menos campos que Neon; no completar metadatos inexistentes mediante suposiciones.
- No compartir un `DataFrame` global entre usuarios; aislar estado por sesión y limitar el tiempo de retención de archivos temporales.

## 6. Persistencia e idempotencia

Una transacción escribe persona, examen y todas sus mediciones, o no escribe nada. `source_sha256` de documento único impide guardar dos veces el mismo archivo. No equiparar dos documentos distintos solo porque coincidan fecha/peso; informar potencial duplicado. No asumir que IDs de diferentes establecimientos son globales y únicos; documentar `source_namespace` y futura conciliación.

La exportación genera un nombre distinto **cada vez que se exporta**: hash de contenido + UTC de alta resolución; dos exportaciones iguales pueden tener el mismo hash, pero timestamp diferente. Si se desea identidad de archivo estrictamente criptográfica, añadir un sufijo aleatorio o escritura exclusiva para evitar carreras.

## 7. Decisiones de reconstrucción

- **Monolito modular** de Python para bajo volumen, sin microservicios prematuros.
- PostgreSQL sirve historial confirmado; CSV sirve movilidad, recuperación y análisis sin dependencia de servicio.
- No construir pipeline hacia Databricks hasta que haya un caso analítico y controles de privacidad.
- No cargar imágenes identificables en Hugging Face Space público. El entorno que maneje datos reales debe ser privado, autenticado y auditado.
- Las dependencias se reproducen por `requirements.txt`; en una reconstrucción, fijar un archivo de bloqueo probado para estabilidad y revalidar compatibilidades de GPU/Gradio.
