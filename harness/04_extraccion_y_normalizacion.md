# 04 — Motor de extracción, OCR, plantillas e idioma

## 1. Entradas soportadas

- PDF digital: texto nativo con PyMuPDF y lectura ordenada, manteniendo páginas.
- PDF escaneado: renderizado controlado de páginas + OCR por imagen.
- JPG/JPEG/PNG: PIL/EXIF para orientación y verificación de tamaño, después EasyOCR.
- Rechazo de extensiones renombradas, archivos corruptos, protegidos por contraseña, sin contenido, demasiado grandes o con páginas excesivas.

La capa Python debe producir objetos Pydantic con `Measurement` y `ExtractionResult`, independientes de la UI. Un test nunca debe necesitar servicio externo ni informe personal identificable.

## 2. Problema de las tablas InBody

Los informes tienen tablas, barras, ejes con cifras de referencia, siluetas corporales, columnas segmentales, bloques superpuestos y valores sin unidad repetida por celda. **Extraer texto en orden lineal no basta**.

Reglas:

1. EasyOCR devuelve `detail=1`: texto, confianza y caja delimitadora. Conservar (x, y, ancho, alto), posición/página y fuente de OCR.
2. Normalizar coordenadas respecto al tamaño de página; aplicar cada parser **solo si identifica su plantilla** con señales suficientes.
3. Las cajas de resultado deben excluir ejes, límites de referencia y etiquetas que no son valores observados.
4. Conservar signos negativos en control de peso/grasa; no insertar un signo basándose en una expectativa.
5. No completar valores perdidos mediante resultados de otras regiones o exámenes anteriores.
6. La fuente OCR es un **candidato**; toda extracción densa requiere revisión visual, especialmente cifras pequeñas y ángulo de fase.

## 3. Clasificación por plantilla

| Familia | Archivo/política | Cuidado especial |
| --- | --- | --- |
| InBody 580 identificado | `inbody_mvp/layouts.py` | Tablas independientes, unidades, porcentajes de referencia y fase segmental |
| Plantilla en español con siluetas | `inbody_mvp/layouts_es.py` | Disposición segmental y 20/100 kHz; no deducir modelo sin evidencia |
| Otras | `inbody_mvp/extractor.py` parser conservador | Mantener desconocidos, no aplicar coordenadas fijas de otra plantilla |

Una plantilla InBody 580 puede aparecer en inglés u otro idioma; **modelo** y **lengua** son campos separados. El idioma determina traducción de etiquetas, no identidad del dispositivo.

## 4. Detección del idioma

`idioma_reporte` acepta exactamente `ES`, `EN` y `UNKNOWN`. Detector actual: `inbody_mvp/language.py`, con búsqueda conservadora de **varias** señales independientes en encabezados y métricas; no asumir idioma por país, edad, cédula o nombre de archivo.

Ejemplos de señales:

- `ES`: «Análisis de la Composición Corporal», «Masa Muscular Esquelética», «Porcentaje de Grasa Corporal».
- `EN`: «Body Composition Analysis», «Skeletal Muscle Mass», «Percent Body Fat».
- `UNKNOWN`: solo «InBody 580», OCR ilegible, una sola señal o señales contradictorias.

El usuario puede corregir el idioma antes de guardar. Persistir la selección revisada en `hj_exams.idioma_reporte`, preservando original de cada etiqueta en `hj_measurements.original_label`. La categorización y el código de medición son independientes del idioma.

## 5. Metadatos del examen

- `id_persona`: ID del reporte; no dar por sentado que es documento nacional verificado.
- `modelo_inbody`: solo si es legible o confirmado por el usuario.
- `timestamp`: fecha y hora; si el reporte solo incluye fecha, dejar hora pendiente. No atribuir zona horaria si no consta.
- `edad`: calcular desde nacimiento y fecha de examen únicamente si ambas son inequívocas y válidas; en otro caso permitir «reportada por el informe» o desconocida.
- `source_sha256`: hash de **archivo original** para control de duplicados (diferente al hash de contenido del CSV exportado).
- `archivo/tipo/página`: metadatos de origen; evitar conservar datos personales en logs.

## 6. Desambiguación de métricas

- `segmental_lean_mass` ≠ `skeletal_muscle_mass`.
- `body_fat_mass` (kg) ≠ `body_fat_percentage` (%).
- «Porcentaje segmental 97 %» puede ser porcentaje frente a referencia; **no** implica que el segmento tenga 97 % de músculo.
- «Impedancia 20 kHz / 100 kHz» debe producir filas diferentes por segmento+frecuencia.
- «Ángulo de fase» puede referirse a cuerpo completo o un segmento. No inferir 50 kHz como valor por defecto.
- En datos desconocidos, registrar etiqueta, valor, unidad y `sin_clasificar` en lugar de descartar.
- El historial gráfico impreso en el reporte no puede convertirse en exámenes históricos sin un parser explícito y fechas verificadas.

## 7. Criterios de aceptación específicos

- **OCR-01:** dado PDF digital sintético con varias métricas, se extraen texto, fecha, metadatos y candidatos sin OCR obligatorio.
- **OCR-02:** dado PDF escaneado sintético, se invoca OCR y se conserva referencia de página.
- **OCR-03:** dado imagen válida y lector OCR simulado con cajas, las medidas se asignan a celdas sin interpretar ejes como resultados.
- **OCR-04:** para plantilla ES con impedancia a 20/100 kHz y cinco regiones, 10 candidatos distintos y correctos cuando aparecen en fixtures.
- **OCR-05:** un archivo con nombre `.png` pero firma PDF es rechazado.
- **OCR-06:** ausencia de fecha/hora o unidad no produce valores inventados.
- **OCR-07:** no se capturan fechas/medidas del gráfico de historial como examen vigente.
- **OCR-08:** una plantilla no reconocida produce advertencias y/o extracción conservadora, sin aplicar coordenadas arbitrarias.
- **OCR-09:** ES/EN/UNKNOWN se determina conservadoramente y puede corregirse en la UI.
- **OCR-10:** comparar resultados reales anonimizados con un conjunto anotado manualmente; documentar precisión y falsos positivos por plantilla antes de afirmar soporte completo.

## 8. Nuevas plantillas: protocolo de incorporación

1. Crear fixture sintético de dimensiones similares con rótulos y cifras ficticias; nunca registrar un reporte real.
2. Anotar regiones normalizadas, encabezados distintivos, unidades y semánticas.
3. Implementar detector específico y extractor con salida `Measurement` común.
4. Probar variaciones de resolución, OCR que fragmenta/une textos, comas decimales y referencias en ejes.
5. Probar que **no** detecta otras plantillas por error.
6. Realizar prueba manual en entorno privado con consentimiento y anonimización, anotar límites y crear regresiones **sintéticas**.
7. Mantener soporte previo y no degradar los tests existentes.
