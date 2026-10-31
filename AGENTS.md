# AGENTS.md — Health Journey

## Estado real y dirección técnica (31 de octubre de 2026)

Este repositorio implementa progresivamente **InBody Hub**, primera fase de Health Journey. **Gradio** es la única interfaz web del MVP: el punto de entrada es `app.py` y el Space usa `sdk: gradio` con ZeroGPU. **Pydantic** valida los datos, **PyMuPDF** extrae texto de PDF, **EasyOCR** procesa JPG/PNG y páginas escaneadas, y **Pandas** permite revisar/exportar. **Plotly** se reserva para un dashboard de tendencias integrado en Gradio (`gr.Plot`) en la siguiente fase.

**No desarrollar ni reintroducir Dash, Flask o React como interfaces.** Mantener `app.py` como entrypoint. No sustituir el SDK de Gradio ni romper ZeroGPU sin una necesidad técnica verificada y autorización expresa.

## Funcionalidad implementada

- Carga de **PDF, JPG, JPEG y PNG** desde `app.py` (límite 15 MB y 8 páginas para PDF).
- Extracción de texto digital con PyMuPDF; OCR EasyOCR para archivos escaneados e imágenes.
- Clasificación conservadora de mediciones conocidas; admite variables desconocidas, segmentos y frecuencias (por ejemplo, ángulo de fase).
- Revisión humana con `gr.Dataframe`; extracción, etiquetas, unidades y valores son **candidatos**.
- Exportación **CSV borrador** con siete columnas: `id_persona`, `modelo_inbody`, `timestamp`, `variable_medida`, `unidad_medida`, `valor_medida`, `edad`.
- Vista informativa de Dashboard futuro y pestaña Proyecto que muestra `README.md`.

**No implementado:** identificación verificada, confirmación persistente, base de datos, deduplicación histórica, autenticación, analítica longitudinal real, gráficas históricas, TrOCR o asistente virtual.

## Organización

- `app.py`: componentes y eventos Gradio; mantener la lógica de extracción separada.
- `inbody_mvp/extractor.py`: lectura PDF/imágenes, OCR de respaldo, Pydantic y clasificación inicial.
- `inbody_mvp/layouts.py`: interpretación conservadora de celdas por coordenadas para el formato InBody 580; no confundir ejes y porcentajes de referencia con mediciones.
- `inbody_mvp/review.py`: tabla de revisión, validación de ediciones, exportación CSV.
- `tests/test_inbody_mvp.py` y `tests/test_review.py`: pruebas unitarias.
- `requirements.txt`: dependencias de ejecución.
- `.github/workflows/deploy-huggingface.yml`: sincroniza `app.py`, `README.md`, `requirements.txt` y los módulos Python de `inbody_mvp/` con el Space `jaqo/health-journey`.
- `docs/despliegue-hugging-face.md`: instrucciones de despliegue.

## Principios de extracción y almacenamiento

1. **Una fila por medición.** Las nuevas variables se agregan como nuevas filas, nunca requieren nuevas columnas en la tabla analítica.
2. **Nada de datos inventados:** faltantes/ambiguos permanecen vacíos; no sustituir por cero ni suponer unidades o timestamps.
3. **Clasificación y dimensión independientes:** conservar etiqueta original, categoría, unidad, segmento, lateralidad, frecuencia y trazabilidad.
4. **Separar masa muscular esquelética de masa libre de grasa.** No equiparar porcentajes relativos a referencia con porcentajes de composición corporal.
5. **Ángulo de fase:** diferenciar cuerpo completo y segmentos, respetar frecuencia (kHz) si aparece; no suponer 50 kHz.
6. **Edad:** calcular desde fecha de nacimiento y fecha del examen si ambas existen; distinguir de edad transcrita.
7. **Identidad:** el ID del reporte no necesariamente es una cédula verificada; no mezclar personas.
8. **Comparabilidad:** no graficar como equivalentes mediciones de definiciones, modelos o frecuencias incompatibles.
9. **Privacidad:** jamás incluir documentos reales, IDs reales, datos médicos o secretos en repositorio, ejemplos, pruebas o logs públicos. QA público solo con archivos ficticios o anonimizados.

## Flujo de trabajo para agentes

- Leer `README.md`, `especificacion.md` y este archivo antes de modificar arquitectura.
- Implementar cambios pequeños y verificables. No declarar disponibles funciones que solo estén previstas.
- No publicar ni alterar credenciales; las claves de Hugging Face están en secretos de GitHub, no en el código.
- No desplegar, hacer merge ni push a `main` sin autorización del usuario.
- Preservar el encabezado YAML de `README.md`: `sdk: gradio`, `app_file: app.py`.
- Mantener separado el motor Python de la UI para poder extender el dashboard Gradio + Plotly sin reescribir la extracción.
- Antes de finalizar, ejecutar `python -m pytest -q tests/test_inbody_mvp.py tests/test_review.py tests/test_inbody_layouts.py` y revisar la compilación sintáctica.
- No afirmar que se ha validado el Space ni el OCR real con reportes auténticos si no hay pruebas de ello.

## Hoja de ruta

1. Completar y probar extracción en reportes InBody reales **anonimizados** de diferentes modelos, reforzar la clasificación y revisión.
2. Almacenar exámenes confirmados con trazabilidad, control de duplicados y acceso privado en PostgreSQL.
3. Crear **dashboard Gradio + Plotly**: filtros por persona, fecha, medida, unidad, región, segmentos (brazos, piernas, tronco), gráficas de líneas, grasa versus músculo y ángulo de fase (global/segmental/frecuencia).
4. Expandir posteriormente a módulos Training y Nutrition; Medical Hub requiere controles clínicos adicionales.

La documentación del reto OBS de semana 2 describe estados históricos y no debe confundirse con las capacidades actuales.

## Validación de formatos densos

- EasyOCR debe devolver `detail=1` para preservar coordenadas y texto; el resumen de texto sin posiciones no basta para tablas InBody.
- Para InBody 580 se usan celdas específicas en `inbody_mvp/layouts.py`; no aplicar esas coordenadas a equipos diferentes.
- No agregar reportes reales ni capturas con cédulas o datos médicos a los tests o al repositorio.
- Los resultados espaciales son candidatos no confirmados: validar visualmente números, signos, unidades, segmentos y porcentajes contra sus referencias originales.
- El historial impreso dentro de una hoja InBody no debe mezclarse automáticamente con el examen actual.

## Persistencia Neon y clasificación de idioma (implementación experimental)

- El proyecto Neon `health-journey` y la base `health_journey` existen con tablas `hj_persons`, `hj_exams`, `hj_measurements`, `hj_measurement_catalog` y vista `hj_measurements_long`. El DDL está en `db/schema.sql`; no ejecutarlo de manera destructiva.
- Clasificar `idioma_reporte` en `ES`, `EN`, `UNKNOWN` desde encabezados mediante `inbody_mvp/language.py`. Pedir revisión humana si no hay suficiente evidencia; el idioma se almacena por examen.
- La capa `inbody_mvp/storage.py` escribe las mediciones revisadas transaccionalmente; necesita `DATABASE_URL` TLS y `ENABLE_PERSISTENCE=1`. No leer ni imprimir credenciales, ni almacenar PDFs o imágenes reales en Git.
- **Prohibido activar guardar en un Space público** sin autenticación/autorización y controles específicos de información médica. El código fuerza `SPACE_ID` a deshabilitar la escritura, además de requerir configuración explícita.
- `hj_measurements_long` conserva siete columnas y no contiene `idioma_reporte`; el idioma y la etiqueta original se consultan en las tablas base. Nuevas métricas agregan filas y entradas al catálogo, no nuevas columnas.
- Los tests `tests/test_language_storage.py` no requieren conexión a Neon ni usan datos personales reales.
- Guía de operación: `docs/neon-postgres.md`.
