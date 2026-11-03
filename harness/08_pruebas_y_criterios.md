# 08 — Harness de pruebas, criterios de aceptación y puertas de calidad

> **Aceptación vigente (2026-11-03):** ver [AC-V-01…AC-V-12](00_estado_vigente_y_trazabilidad.md#3-matriz-de-aceptación-operativa), con pruebas, estado, pendientes y requisitos tecnológicos. Los **36 CA y 10 CS** conservados más abajo se preservan como visión/histórico porque el verificador de harness comprueba sus IDs: no se declaran aprobados automáticamente. Los criterios sobre EasyOCR, exportación CSV de siete columnas y selector CSV+Neon no son la UI principal de `main`. Las suites de CI son sintéticas (no Space real, Gemini o Neon); PR #72 para multiturno/prompts sigue sin fusionar y tiene 317 tests en su rama. Exigir evidencia visual móvil, E2E y aislamiento multitenant antes de dar por aceptado un lanzamiento.


**Normativa:** cada criterio debe tener resultado **APROBADO / FALLIDO / PENDIENTE / NO APLICA**, evidencia verificable (test, log saneado o captura anonimizada), commit y entorno. «El código parece soportarlo» no equivale a aprobado.

## 1. Estrategia de pruebas

1. **Unitarias offline:** extracción de texto, detección de plantilla/idioma, Pydantic, CSV, nombre de exportación, CSV múltiple y selección Plotly con entradas sintéticas.
2. **Integración offline:** Gradio y eventos con OCR/Neon simulados; no descargar modelos ni consultar recursos reales en CI.
3. **Integración PostgreSQL:** BD de QA efímera, migración, CRUD permitido, rollback de errores, duplicación, vistas y permisos mínimos. Jamás usar datos privados de producción.
4. **E2E de Space:** OAuth real, variables bien/mal configuradas, login autorizado/no autorizado, OCR con archivo sintético, exportación, guardado y consulta.
5. **Pruebas de compatibilidad:** dos o más plantillas, ES/EN, cambios de resolución, faltantes, valores ambiguos.
6. **Pruebas de seguridad:** rutas no autenticadas, manipulación de ID de persona, CSV con fórmulas y archivos adversariales, logs sin datos privados.

No agregar al repositorio informes reales; fixtures deben contener exclusivamente identidad y cifras ficticias.

## 2. Criterios funcionales comprobables

| ID | Dado / cuando / entonces | Evidencia requerida |
| --- | --- | --- |
| CA-01 | Dado PDF digital válido, al cargarlo se extrae texto sin necesitar OCR en la página legible. | Test PyMuPDF |
| CA-02 | Dado PDF escaneado, se invoca OCR y se registra página/método. | Test OCR simulado |
| CA-03 | Dado JPG y PNG válidos, se generan candidatos equivalentes al texto disponible. | Test tipos |
| CA-04 | Si contenido y extensión difieren, se rechaza antes de procesar. | Test adversarial |
| CA-05 | Si supera límites de tamaño/páginas/píxeles, se informa error controlado. | Tests límites |
| CA-06 | La extracción InBody 580 no confunde marcas de ejes con mediciones. | Fixture espacial |
| CA-07 | La plantilla ES con siluetas no mezcla piernas/brazos ni porcentajes de referencia. | Fixture ES |
| CA-08 | Impedancia 20/100 kHz en cinco regiones genera diez observaciones separadas cuando el fixture las contiene. | Test frecuencia |
| CA-09 | Una etiqueta no reconocida se conserva como dato pendiente. | Test parser |
| CA-10 | Dado encabezado claro español se captura `ES`; inglés `EN`; ambiguo `UNKNOWN`. | Tests idioma |
| CA-11 | Se puede corregir idioma, unidad, valor, variable y metadatos antes de confirmar. | Prueba UI |
| CA-12 | Sin hora comprobable no se inventa timestamp; sin DOB/edad no se inventa edad. | Test incertidumbre |
| CA-13 | El usuario puede exportar CSV **sin** `DATABASE_URL`. | Test app offline |
| CA-14 | El CSV mantiene exactamente las siete columnas y una fila por medida. | Test contrato |
| CA-15 | El nombre de cada exportación contiene hash de contenido + timestamp UTC del momento de exportar, sin PII. | Test nombre |
| CA-16 | Dos exportaciones sucesivas del mismo contenido generan nombres distintos sin sobreescritura. | Test colisión/repetición |
| CA-17 | Cargar varios CSV compatibles produce una tabla unificada sin tocar PostgreSQL. | Test con mock BD |
| CA-18 | CSV duplicados exactos no duplican las mediciones en el dashboard; informar omisiones. | Test dedupe |
| CA-19 | CSV inválidos (headers, UTF-8, valor no finito, extras, demasiado grandes) se rechazan o marcan sin ejecutar código. | Tests negativos |
| CA-20 | Una fila sin fecha aparece en tabla pero no crea un punto cronológico falso. | Test fechas |
| CA-21 | Al seleccionar fuente Neon se consulta solo tras autorización y se obtienen datos confirmados. | Integración/Space |
| CA-22 | Al cambiar la fuente del dashboard no se mezclan registros de CSV y Neon automáticamente. | Test aislamiento |
| CA-23 | Los filtros de persona, fecha, unidad, modelo, variable, segmento y frecuencia funcionan y muestran estado vacío correctamente. | Test UI/plot |
| CA-24 | Plotly dibuja líneas temporales por serie compatible; no une modelo, definición, unidad ni frecuencia distintos. | Test Plotly |
| CA-25 | Grasa kg, % de grasa, masa muscular esquelética y masa magra segmental se etiquetan separadamente. | Test semántico |
| CA-26 | El guardado Neon ocurre solo tras confirmación explícita y en una sola transacción. | Test integración BD |
| CA-27 | Reimportar archivo fuente de hash idéntico no inserta un segundo examen. | Test idempotencia |
| CA-28 | Error en una medida revierte toda la transacción; no quedan exámenes parciales. | Test rollback |
| CA-29 | El catálogo permite nuevas claves con etiquetas ES/EN sin nuevas columnas de tabla. | Test esquema |
| CA-30 | El histórico gráfico impreso no se registra como exámenes adicionales sin fechas verificadas. | Test plantilla |
| CA-31 | Gradio inicia desde `app.py`, sin importar Dash/Flask/React como UI. | Build/inspección |
| CA-32 | Cada módulo nuevo importado por `app.py` está incluido en la publicación del Space. | Test workflow |
| CA-33 | Space/BD desconectado: importación y visualización CSV continúan funcionando. | Test degradación |
| CA-34 | Un cambio de plantilla no rompe fixtures anteriores. | Regresión completa |
| CA-35 | La aplicación informa explícitamente si Guardar está deshabilitado; no desaparece silenciosamente. | Prueba UI |
| CA-36 | Ningún botón declara «guardado» antes de una respuesta positiva de la transacción. | Test error SQL |

## 3. Criterios de seguridad obligatorios

| ID | Condición | Evidencia |
| --- | --- | --- |
| CS-01 | Secretos nunca se imprimen ni se versionan; `.env` ignorado. | Revisión de repo + detección secretos |
| CS-02 | Usuario Space no autenticado/no autorizado no lee ni escribe en Neon. | Pruebas llamadas al backend |
| CS-03 | Cambiar parámetros manualmente no elude control de identidad; en multiusuario, comprobar propiedad por fila. | Prueba acceso cruzado |
| CS-04 | Rol Neon del Space carece de `DELETE`, `CREATEROLE` y membresía administrativa. | Consultas de privilegios |
| CS-05 | Todo tráfico PostgreSQL usa TLS y credencial de rol mínimo. | Config/validación conexión |
| CS-06 | Las páginas públicas/Space público no exponen informes de salud ni datos personales. | Revisión despliegue |
| CS-07 | Logs, CI, errores y métricas no muestran identificadores ni documentos originales. | Inspección de logs |
| CS-08 | Los uploads y CSV no se comparten entre sesiones y cumplen retención/limpieza. | Test aislamiento y limpieza |
| CS-09 | Importar CSV nunca escribe a Neon, aun si `ENABLE_PERSISTENCE=1`. | Prueba con spy SQL |
| CS-10 | Rechazar fórmulas CSV, valores infinitos, columnas extra y desbordes sin ejecución de código. | Suite maliciosos |

## 4. Casos de rendimiento / límites

- 1 PDF digital, 1 PDF escaneado, 1 JPG y 1 PNG sintéticos.
- 2 plantillas diferentes y 2 idiomas, una tercera desconocida.
- 25 CSV pequeños de ejemplo, con registros duplicados y fechas faltantes.
- 100 000 filas totales como techo inicial **objetivo**, ajustable tras medir memoria/CPU; no prometer capacidad real sin benchmark.
- Consulta paginada/limitada desde Neon; no cargar todas las personas al abrir el Space.
- Al fallar OCR/GPU, interfaz ofrece error claro sin guardar automáticamente datos parciales.

## 5. Comandos mínimos para CI

```bash
python -m compileall -q app.py inbody_mvp
python -m pytest -q tests
python harness/validar_reconstruccion.py
```

Los tests de integración Neon requieren una base efímera y secretos de CI específicos, nunca la base con datos reales.

## 6. Matriz de «Definition of Done»

Una historia se cierra solo si:
1. Contrato documentado y compatible con `harness/`.
2. Unit tests y regresiones sintéticas en verde.
3. Prueba manual anonimizada en entorno de despliegue correspondiente.
4. Seguridad y privacidad revisadas según exposición.
5. README/AGENTS/harness actualizados si cambia el diseño.
6. Migración o rollback disponible si cambia el esquema.
7. Evidencia del PR y un responsable que confirma la salida.

**Regla final:** el estado `PENDIENTE` de una prueba bloqueante no debe convertirse en `APROBADO` porque se creó un botón o una función.

## 7. Criterios experimentales de IA por secciones

**Importante:** el resultado de pruebas sintéticas confirma la lógica de
integración, **no** la precisión de PaddleOCR sobre los JPG personales.
Aplicar [el protocolo de evaluación](../docs/ocr-secciones-ia.md#7-evaluación-de-precisión-definir-primero-la-verdad-de-referencia).

| ID | Condición para aprobar | Estado inicial |
| --- | --- | --- |
| IA-01 | Detector real produce cajas válidas en muestras anonimizadas de varios modelos InBody | PENDIENTE |
| IA-02 | EasyOCR regional conserva coordenadas absolutas y etiqueta semántica con evidencia visual | PARCIAL — test sintético |
| IA-03 | Métricas por sección: valor, unidad, segmento y frecuencia coinciden con ground truth | PENDIENTE |
| IA-04 | Ningún eje ni punto del historial global es almacenado como examen actual | PENDIENTE |
| IA-05 | Fecha/hora del encabezado no se confunden con DOB; no se inventan valores | PENDIENTE en conjunto real |
| IA-06 | Layout + OCR supera baseline en exact match sin elevar falsos positivos críticos | PENDIENTE |
| IA-07 | Recursos de CPU/GPU, latencia p95 y compatibilidad de ZeroGPU verificados | PENDIENTE |
| IA-08 | Revisión humana, permisos, consentimiento y protección de datos no se degradan | PENDIENTE E2E |

Para comprobar IA-03 e IA-06 construir un ground truth privado para cada
uno de los 22 reportes de referencia: alias interno, modelo, sección, código,
unidad, valor, segmento, timestamp y posición. Revisar cifras directamente
de la imagen original; no utilizar resultados OCR como verdad de referencia.
Comparar baseline, modelo visual y un posible VLM **solo si éste se implementa**.
Registrar errores por sección y modelos incompatibles, además de promedios.

**No activar el modo experimental en producción ni considerar exactos los datos
de Neon hasta satisfacer los criterios de calidad y privacidad.**
