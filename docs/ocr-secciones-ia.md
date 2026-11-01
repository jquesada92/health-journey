# OCR por secciones usando IA de layout (fase experimental)

## Objetivo

Reducir atribuciones incorrectas de números en JPG/PDF InBody. El flujo
anterior detecta texto con EasyOCR, luego reglas y posiciones. En documentos
con varias columnas y ejes gráficos, el OCR global puede intercalar cifras.

**Nuevo flujo, solo para QA:**

1. **PP-DocLayout-S (visión por computador, modelo preentrenado local)** detecta
   regiones genéricas: tablas, textos, encabezados, gráficos. No es un modelo
   entrenado específicamente para InBody.
2. En cada región detectada, **EasyOCR vuelve a leer el recorte**. Los resultados
   se reubican a coordenadas de la imagen original.
3. Las **etiquetas OCR de encabezado** asignan la sección semántica:
   composición corporal, músculo-grasa, obesidad, magro por segmentos, grasa
   segmental, parámetros, impedancia o historial.
4. El historial se **excluye** de los resultados actuales; los recortes sin
   sección reconocible no se consideran fiables.
5. Se reconcilian bloques OCR por proximidad y confianza con los existentes.
   Los extractores de métricas y Pydantic siguen funcionando como antes; la
   revisión humana es obligatoria antes de exportar/guardar.
6. Registrar diferencias de candidato, sección y fuente en los reportes de
   pruebas; **no** dar por exactos los resultados solo por confianza del OCR.

## Activación y despliegue

El modo está **desactivado por defecto**. El Gradio Space se mantiene con sus
dependencias normales, sin PaddleOCR adicional. Para evaluar IA por secciones,
preparar un ambiente privado QA compatible:

```sh
python -m pip install -r requirements.txt
python -m pip install -r requirements-ai.txt
ENABLE_AI_SECTION_OCR=1 python app.py
```

Cuando se valide compatibilidad en Hugging Face ZeroGPU y se demuestre una
mejora medible, agregar las dependencias de `requirements-ai.txt` a la
instalación del Space (o ejecutar el modelo en un servicio privado compatible).
**Solo entonces** activar `ENABLE_AI_SECTION_OCR=1` en Hugging Face.
Si falta el runtime del modelo y se activa el modo, la extracción devuelve un
error claro; no oculta el fallo ni afirma haber aplicado IA.

El modelo preentrenado puede descargar pesos de manera separada, pero
**no se envían imágenes InBody a servicios de terceros**. No compartir JPG
personales con un endpoint público ni subirlos a GitHub.

## Riesgos y límites

- El modelo genérico detecta tablas y gráficos, **no interpreta clínicamente**
  cada métrica ni distingue con total fiabilidad todas las secciones InBody.
  Las etiquetas semánticas siguen requiriendo OCR y reglas. Un modelo
  específico de InBody requeriría anotaciones de secciones y entrenamiento.
- Detección de tablas imperfecta y recortes que omitan títulos pueden
  producir campos incompletos. Se mantiene el OCR global como baseline.
- Los candidatos nuevos se priorizan si tienen puntuación de OCR
  considerablemente mayor y misma posición. No equivale a certeza.
- Para comprobar que mejora, crear un dataset privado revisado a mano de
  los 22 reportes recuperados: ground truth por examen, variable, segmento,
  unidad, valor, fecha y región. Medir precisión/exact match por campo,
  recall, falsos positivos del historial, tiempo y RAM con y sin IA.
- **No cambiar Neon, publicar exámenes ni incorporar mediciones inferidas
  automáticamente** hasta pasar la validación de extremo a extremo.

## Contratos de prueba

`tests/test_ai_section_ocr.py` usa un modelo de layout falso con la
**misma respuesta estructural** que el modelo real, para verificar el orden
«detectar IA → recortar → OCR», la reasignación de coordenadas, filtrado
de historial y de regiones sin etiqueta. Esas pruebas **no miden** la
precisión del modelo preentrenado con JPG reales.

Referencia técnica oficial:
https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/layout_detection.en.md
