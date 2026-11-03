# Hito de la semana 2 · Health Journey

> **Documento histórico académico:** registra un hito previo, no el alcance activo en `main` del 2026-11-03. Para el menú actual de cuatro módulos, Gemini InBody, FitNotes, chat, privacidad prelogin, criterios y tecnologías, usar [inventario vigente](../harness/00_estado_vigente_y_trazabilidad.md). No confundir la entrega de una semana con pruebas de seguridad, CI ni funcionamiento del Space.


## Contexto breve para el debate

Health Journey es un proyecto modular orientado a un asistente virtual que ayude a dar seguimiento a hábitos, entrenamientos y objetivos de bienestar mediante información confiable reunida en un mismo lugar. La visión contempla tres fases: (1) consolidación de InBody, (2) integración de logs de entrenamiento y macronutrientes, y (3) incorporación futura de exámenes clínicos. Para el reto de OBS, empezamos **solo por InBody**, porque los reportes pueden llegar desde establecimientos distintos en PDF de texto, PDF escaneados, PNG o JPG.

## Ficha de cinco líneas para publicar en Blackboard

1. **Problema:** Los datos de salud y progreso físico están dispersos entre aplicaciones que no se comunican y documentos en múltiples formatos; por ejemplo, cinco pruebas InBody en una tienda y seis en otra quedan en historiales separados, dificultando seguir una tendencia continua.
2. **Usuario:** Personas que entrenan y desean comprender su evolución física sin transcribir manualmente reportes obtenidos en distintos centros y aplicaciones.
3. **Qué hará la app:** (1) recibir reportes InBody en PDF, PNG y JPG, (2) extraer y validar mediciones y datos del examen y (3) consolidar un historial por persona y fuente para consultar la evolución.
4. **Pieza de IA:** Usaremos un **modelo de Hugging Face (TrOCR Small Printed)**, combinado con EasyOCR y validaciones Python, para reconocer texto de reportes InBody sin llamadas a APIs de pago; el usuario revisará las mediciones extraídas.
5. **Enlace a la versión 0:** https://jaqo-health-journey.hf.space/ (**pendiente de comprobar en ventana de incógnito antes de publicar**).

## Aclaración para las semanas 2 y 3

La versión 0 **solo permite cargar imágenes y obtener texto con EasyOCR**. No admite PDF, no extrae mediciones estructuradas, no consolida historiales y todavía **no integra TrOCR**. La ficha anterior describe la intención de la fase 1 y no debe confundirse con capacidades ya implementadas. La semana 3 incorporará la pieza de IA y registrará una prueba y una mejora a partir del feedback.

## Prueba de compañero (semana 3)

Registrar al menos: qué se probó, qué funcionó, dónde surgió una dificultad y qué mejora se sugiere. Documentar una mejora concreta derivada de la prueba.

Más detalle: [especificacion.md](../especificacion.md) y [README.md](../README.md).
