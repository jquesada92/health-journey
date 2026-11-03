# Arquitectura de extracción InBody: detección visual de secciones + OCR + validación

> **Investigación histórica/experimental (2026-11-03):** aquí se conservaron estrategias de OCR y evaluación espacial; no representan controles activos de la UI actual. Los módulos locales OCR/editor pueden seguir versionados para tests, pero el Space distribuido consume Gemini Flash para extracción de PDF/JPG/PNG. La migración del prompt InBody a un archivo separado y la corrección del chat científico están en PR #72 **sin merge**. Evaluar cualquier propuesta OCR nueva con fixtures sintéticos, tiempo/coste y regresiones, no con documentos privados. [Estado y pruebas](../harness/00_estado_vigente_y_trazabilidad.md).


> **Estado:** experimento implementado en la rama `feature/ai-layout-first-inbody-ocr`, no validado como mejora de precisión ni desplegado en el Space de producción. **No confundir pruebas unitarias con una evaluación del modelo sobre imágenes reales.** El modo IA está desactivado por defecto.

## 1. Problema que resolvemos

Los reportes InBody contienen información distribuida en tablas, barras con ejes de referencia, dibujos corporales, varias columnas y gráficos con registros anteriores. Un OCR que recorra toda la imagen puede leer bien los caracteres y, aun así, **asociar un número a la métrica, lado corporal, unidad o fecha incorrectos**.

Ejemplos de fallos conocidos:
- Mezclar la fecha de nacimiento con la fecha/hora del examen, ya que aparecen en columnas próximas.
- Leer cifras de una escala o un porcentaje de referencia como si fueran mediciones actuales.
- Confundir *masa grasa corporal*, *porcentaje de grasa corporal* y *masa muscular esquelética*.
- Asignar valores del brazo izquierdo al derecho o confundir masa segmental con porcentaje.
- Incluir puntos del gráfico de evolución histórica como medidas del examen actual.
- No reconocer un encabezado si EasyOCR combina etiquetas que visualmente pertenecen a columnas diferentes.

**Objetivo:** que el sistema comprenda primero **dónde están las secciones** del documento, lea después cada región con OCR, y solo entonces clasifique y valide los campos. La IA debe reducir errores, **no inventar resultados**.

## 2. Diferencia entre «detectar una región» y «comprender una sección InBody»

Un detector de layout (diseño de página) es un modelo de visión por computador que ha aprendido patrones visuales a partir de documentos anotados: límites de tablas, bloques de texto, títulos, gráficos y sus relaciones espaciales.

Cuando recibe una imagen, devuelve predicciones del tipo:

```json
{
  "label": "table",
  "score": 0.92,
  "coordinate": [140, 330, 780, 670]
}
```

**Este es un ejemplo ficticio de formato de salida, no una predicción de nuestros JPG.** Las coordenadas delimitan un rectángulo de la imagen original y `score` indica la confianza de detección de la **región**, no la precisión de los valores médicos.

El modelo visual genérico **no sabe por sí solo** que esa tabla se llama «Análisis Músculo-Grasa». En la propuesta actual, EasyOCR lee el título de la región y un clasificador explícito de etiquetas lo asigna a una sección conocida. Por eso hay tres operaciones independientes:

1. **Detección visual (IA):** «aquí hay una tabla».
2. **OCR:** «en el título de esa tabla pone Muscle-Fat Analysis».
3. **Interpretación semántica (reglas verificables):** «esta tabla pertenece a `muscle_fat`; interpreta sus celdas según ese contexto».

Una probabilidad alta en el paso 1 **no certifica** que los pasos 2 y 3 sean correctos. La clasificación semántica actual sigue siendo por patrones de texto; **no es un VLM** ni un clasificador InBody entrenado específicamente.

## 3. Flujo técnico de extracción

```text
JPG / PNG / PDF
        |
        +--> PDF digital legible --> PyMuPDF (texto nativo)
        |
        +--> Imagen / PDF escaneado
                   |
                   v
          [OPCIONAL] Modelo visual PP-DocLayout-S
                   |
                   v
          Regiones genéricas: table / text / header / chart / ...
                   |
                   v
          Recortes por sección + EasyOCR (texto y bounding boxes)
                   |
                   v
          Identificación semántica por títulos OCR (ES / EN)
                   |
                   +--> sección desconocida: no añadir datos de ese recorte
                   +--> historial: excluir su OCR adicional
                   |
                   v
          Transformar coordenadas del recorte a la página original
                   |
                   v
          Reconciliar con EasyOCR de la página completa
                   |
                   v
          Parsers existentes (plantillas + Regex + geometría)
                   |
                   v
          Pydantic + tabla editable Gradio + revisión visual
                   |
                   v
          CSV / Neon SOLO después de confirmación y consentimiento
```

**Comportamiento real del código actual:**
- Con `ENABLE_AI_SECTION_OCR=0`, no se ejecuta PP-DocLayout-S; sigue el extractor original.
- Con `ENABLE_AI_SECTION_OCR=1`, `extract_document` llama a `inspect_sections` **antes** del OCR global de la imagen y a `merge_section_ocr` para reconciliar candidatos. El resultado continúa pasando por `parse_text`, `extract_inbody580` y `extract_spanish_silhouette`.
- Las regiones reconocidas se recortan, pueden ampliarse para mejorar caracteres pequeños y se vuelven a leer con EasyOCR. Las bounding boxes regresan a coordenadas absolutas.
- Se admiten como candidatos adicionales **solo regiones con un título de sección reconocible**. Los bloques que el detector encontró sin título reconocible no se interpretan como una sección médica.
- Si una nueva detección OCR coincide espacialmente con una existente, la sustituye solo cuando su confianza OCR es sustancialmente mayor (actualmente **+0,10**). La confianza tampoco garantiza exactitud.
- **Límite importante:** el filtro de historial impide añadir nuevos tokens OCR procedentes del recorte etiquetado como `history`, pero **aún no garantiza que el parser global elimine todas las cifras históricas**. Hace falta aislar los extractores por región antes de afirmar exclusión completa. Tampoco existe todavía un parser semántico independiente y exhaustivo por sección; por ahora se mejora la detección de tokens que consumen los parsers existentes.

### Archivos responsables

| Archivo | Responsabilidad |
| --- | --- |
| `app.py` | UI Gradio, llamada de extracción, tabla revisable y callbacks |
| `inbody_mvp/extractor.py` | Orquestación PDF/imagen, OCR global, modelos de medición, fecha y combinación de resultados |
| `inbody_mvp/section_ai.py` | Detección visual opcional, recortes, clasificación por título, OCR regional y reconciliación |
| `inbody_mvp/layouts.py` | Coordenadas y celdas de InBody 580; fecha/hora del encabezado |
| `inbody_mvp/layouts_es.py` | Coordenadas para la plantilla española con siluetas |
| `inbody_mvp/review.py` | Tabla editable y validación del borrador CSV |
| `inbody_mvp/storage.py` / `demo_storage.py` | Contratos de guardado privado y demostración, no extracción de imágenes |
| `tests/test_ai_section_ocr.py` | Pruebas sintéticas del flujo con detector simulado |
| `requirements-ai.txt` | Dependencias experimentales separadas de producción |

## 4. Cómo asignamos significado a las secciones

El detector genérico devuelve clases visuales, no códigos de negocio. La función `classify_section` busca encabezados reconocidos en el texto extraído **dentro de cada región**.

| Título InBody (ejemplos) | Código de sección | Significado esperado |
| --- | --- | --- |
| Body Composition Analysis / Análisis de la Composición Corporal | `body_composition` | Agua corporal, proteínas, minerales, masa grasa |
| Muscle-Fat Analysis / Análisis Músculo-Grasa | `muscle_fat` | Peso, masa muscular esquelética, masa grasa |
| Obesity Analysis / Análisis de Obesidad | `obesity` | IMC, porcentaje de grasa corporal |
| Segmental Lean Analysis / Análisis de Magro por Segmentos | `segmental_lean` | Masa magra por brazo, pierna y tronco |
| Segmental Fat Analysis / Análisis de Grasa Segmental | `segmental_fat` | Grasa por segmento y porcentajes de referencia |
| Research Parameters / Parámetros de investigación | `research` | Variables adicionales, cuando la plantilla las identifique |
| Impedance / Impedancia | `impedance` | Impedancia según segmento y frecuencia |
| Body Composition History / Historial de Composición Corporal | `history` | **No es el examen actual**: requiere extractor histórico separado |

Los ejemplos muestran el **contrato deseado de negocio**. La lista de encabezados que reconoce de verdad el prototipo es la de `OCR_SECTIONS` en `section_ai.py`: aún no hay cobertura de todas las traducciones, variantes y modelos. Un título ausente o mal reconocido hace que la región quede sin clasificar.

Para mejorar la precisión real se necesita asociar cada **medición** a: `section`, `variable_medida`, `segmento`, `unidad_medida`, `valor_medida`, `source_bbox` y evidencia OCR. Actualmente el modelo `Measurement` aún **no almacena todos esos campos de trazabilidad por sección**; es trabajo pendiente.

## 5. Timestamp del encabezado: una regla independiente

La fecha y hora válidas pertenecen a **Test Date / Time** o **Fecha / Hora del test** y no deben obtenerse del gráfico histórico ni del campo DOB.

Ejemplos de formatos impresos:

```text
Test Date / Time
04.10.2026. 10:04
```

```text
Fecha / Hora del test
26.01.2025. 14:20
```

El parser actual primero intenta leer etiquetas explícitas y usa las coordenadas del encabezado cuando la lectura lineal mezcla columnas. Si falta o no es fiable un campo, debe mostrarse como pendiente de revisión; nunca sustituirlo automáticamente por `datetime.now()`, la fecha del correo o la fecha de nacimiento.

La solicitud de **permitir fecha manual solamente cuando OCR falla** es una mejora independiente: debe mostrar cuándo y quién confirmó el timestamp, conservar su procedencia y seguir bloqueando sustituciones silenciosas de una fecha que sí se haya leído correctamente. **No está implementada por el módulo experimental de IA.**

## 6. ¿Por qué no usar directamente un Vision-Language Model (VLM)?

Un VLM recibe conjuntamente píxeles y texto; podría responder qué sección contiene una región y devolver campos estructurados. Esto es diferente del detector de layout genérico.

| Alternativa | Qué aporta | Limitación principal | Estado |
| --- | --- | --- | --- |
| **EasyOCR + Regex + geometría** | Bajo costo y reglas reproducibles; referencia para medir cambios | Fragilidad ante columnas, diseño y OCR defectuoso | Extractor actual |
| **PP-DocLayout-S + OCR por región** | Identifica bloques visuales antes de leer texto; puede recuperar celdas pequeñas | La semántica depende de etiquetas OCR; no resuelve por sí solo todas las tablas | **Experimento opcional implementado, sin benchmark real** |
| **VLM multimodal especializado en documentos** | Posibilidad de razonar sobre estructura y relaciones visuales | Latencia/VRAM, errores plausibles y alucinaciones, privacidad y validación de salida | **Alternativa por evaluar; no implementada** |
| **Detector ajustado con secciones InBody** | Podría aprender regiones InBody concretas | Requiere anotaciones suficientes y reentrenamiento | Idea futura |

Una opción futura es evaluar familias de modelos documentales VLM como PaddleOCR-VL o Qwen-VL en un entorno controlado. **No se ha seleccionado, entrenado ni integrado ninguno**. La elección debe basarse en resultados medidos, licencias, soporte real del runtime y seguridad de los datos.

Ningún modelo, por sí solo, debe autorizar datos médicos para Neon. Las salidas se deben validar contra un esquema cerrado (Pydantic), rangos/unidades/segmentos y revisión visual.

## 7. Evaluación de precisión: definir primero la verdad de referencia

Tenemos **22 reportes InBody principales** y archivos complementarios recuperados de correo. **No están en el repositorio ni sirven todavía como ground truth aprobado**. La evaluación será privada, con acceso controlado, sin subir imágenes personales a GitHub, logs públicos o una API externa.

### Dataset de evaluación

Para cada examen real, registrar manualmente y cotejar con el JPG/PDF original:

| Campo | Ejemplo de esquema (sintético) |
| --- | --- |
| `sample_alias` | `case_001` (sin identificación personal) |
| `template_family` | `inbody_580` o `spanish_silhouette` |
| `section` | `muscle_fat` |
| `metric` | `skeletal_muscle_mass` |
| `segment` | `whole_body` o nulo según métrica |
| `unit` | `kg` |
| `expected_value` | `35.0` (valor inventado para ilustrar) |
| `expected_exam_timestamp` | `2025-01-26T14:20:00` (ejemplo de formato) |
| `source_bbox` | `[x0,y0,x1,y1]` normalizado |
| `verified_by` | Identificador interno del revisor |

Los datos numéricos deben revisarse por persona antes de convertirse en verdad de referencia. Registrar qué medidas son ilegibles, qué modelos faltan y cuáles exigen tratamiento diferente; no completar faltantes por inferencia.

### Experimentos comparables

| Variante | Configuración | Qué determina |
| --- | --- | --- |
| A — Baseline | EasyOCR + parsers actuales; IA deshabilitada | Nivel actual de exactitud |
| B — Layout-first | PP-DocLayout-S + OCR por sección + parsers actuales | Si detectar regiones mejora sobre A |
| C — VLM | Solo si se implementa y justifica | Si la interpretación multimodal supera A y B |

Medir por **plantilla, métrica y sección**:
- **Exact match** de valor numérico, unidad, segmento y fecha/hora (separados, y combinación completa).
- **Precisión, recall y F1** sobre filas de medición (no basta acertar algunos valores).
- **Falsos positivos** extraídos de ejes, porcentajes de referencia e historial.
- **Sección correcta** y precisión de localización de región (IoU si hay bounding boxes anotadas).
- Campos ausentes, errores graves, confianza mal calibrada y frecuencia de intervención humana.
- Latencia media y p95, RAM/VRAM, tiempo de carga, estabilidad y costo por archivo.

**Criterio recomendado antes de activar B:** mejorar la exactitud completa respecto a A sin aumentar falsos positivos críticos de fechas, lados o medidas históricas, y completar pruebas reales en el runtime objetivo. La mejora debe estar sustentada con una tabla de resultados versionada, no solo con tests sintéticos en verde.

## 8. Implementación, entorno y límites de despliegue

Modo experimental, deshabilitado por defecto:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-ai.txt
ENABLE_AI_SECTION_OCR=1 python app.py
```

**Condiciones:**
- `requirements-ai.txt` incluye PaddlePaddle y PaddleOCR como dependencias **opcionales**. La instalación normal del Space no las contiene.
- `PP-DocLayout-S` se inicializa localmente con `device="cpu"` en el prototipo, aun si EasyOCR usa una GPU disponible. No asumir aceleración ni compatibilidad con ZeroGPU.
- `app.py` usa Gradio y EasyOCR; la inicialización y las limitaciones de CPU, GPU, memoria y tiempo deben medirse de forma real.
- El modelo podrá necesitar descargar sus **pesos** del proveedor; esto no implica enviar imágenes del usuario a un servicio remoto de inferencia. No introducir APIs externas de salud sin evaluación explícita.
- Con el flag activado y dependencias ausentes, el extractor debe informar error; no afirmar que ejecutó IA con éxito.
- El modo y sus pruebas se prepararon en una rama; **no está demostrado que la versión publicada en Hugging Face ejecute este componente**.

## 9. Privacidad, almacenamiento y reglas de aceptación

Los reportes contienen datos personales y de salud. En el Space público, el archivo original llega al servidor **antes** del OCR: se debe anonimizar el documento antes de cargarlo o usar un entorno privado. Un ID seudónimo del dashboard **no anonimiza el JPG**.

Reglas:
1. No guardar automáticamente resultados que difieran de la imagen o no puedan verificarse.
2. Mantener el consentimiento separado para **almacenamiento** y **publicación**; ambas opciones comienzan desmarcadas.
3. Nunca registrar imágenes, nombres, OCR completo, identificadores o credenciales en GitHub, logs de CI, modelos remotos o datasets públicos.
4. Conservar trazabilidad de método/modelo/versión/ubicación del valor cuando se implemente esa ampliación; no confundir confianza del detector con confianza de una medición.
5. Mantener el historial fuera de la tabla de medidas del examen actual y no usar valores de otras fechas para rellenar huecos.
6. Comparar con Neon **solo si existen datos efectivamente guardados**; una base vacía no sirve para demostrar exactitud. No escribir mediciones personales no revisadas para crear artificialmente un benchmark.

## 10. Pruebas actuales y próximos hitos

**Implementado y comprobable mediante código:**
- Detección de regiones del modelo local bajo flag, recorte de imagen, OCR adicional y retorno de bounding boxes a coordenadas originales.
- Clasificación semántica conservadora mediante los títulos OCR.
- Exclusión de tokens **adicionales** de recortes de historial y descarte de regiones sin título reconocible.
- Pruebas sintéticas en `tests/test_ai_section_ocr.py` con un detector **simulado**, no el modelo real.

**Aún pendiente (no afirmar que ya funciona):**
1. Ejecutar el modelo real en un entorno privado compatible con las dependencias y obtener logs de compatibilidad sin PII.
2. Generar la tabla de ground truth manual para los 22 reportes y ejecutar A/B.
3. Separar *por completo* el historial y ejes del parser global, no solo del OCR complementario.
4. Exigir correspondencia **sección → métrica → segmento → unidad → valor → posición** con evidencia visual para cada resultado.
5. Medir y demostrar precisión superior y tiempo/recursos aceptables en ZeroGPU.
6. Evaluar VLM únicamente si la mejora de layout + OCR sigue siendo insuficiente.
7. Habilitar un mecanismo excepcional de fecha manual **explícitamente marcado como manual**, cuando la extracción falle, sin reemplazar automáticamente datos correctos.
8. Revisar casos reales de extremo a extremo antes de permitir guardar en Neon sin confirmación.

### Enlaces internos

- [Código del detector y OCR por regiones](../inbody_mvp/section_ai.py)
- [Extractor orquestador](../inbody_mvp/extractor.py)
- [Pruebas sintéticas](../tests/test_ai_section_ocr.py)
- [Requisitos experimentales](../requirements-ai.txt)
- [Contrato de extracción del harness](../harness/04_extraccion_y_normalizacion.md)
- [Criterios de calidad del harness](../harness/08_pruebas_y_criterios.md)

Referencia de documentación de la integración: [PaddleOCR, módulo Layout Detection](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/layout_detection.en.md).
