# Entregable académico · Módulo 1 · Fundamentos de la Programación

**Documento fuente aportado por el estudiante:** `Actividad Sesión 4 - Actividad principal.html` (requisitos docentes, no plantilla Word de Blackboard).  
**Actividad principal:** 60 % del módulo. **Cierre indicado:** 02/11/2026 (fecha ya pasada respecto a esta implementación).  
**Entrega en Blackboard:** un único documento DOCX o PDF, ocho apartados en el orden indicado, sin vídeo obligatorio.

## Apartados oficiales, en orden

1. **Enlaces:** aplicación desplegada y repositorio público con `app.py`, `requirements.txt` y `README.md`.
2. **Problema y usuario:** destinatario, método actual sin la herramienta y papel acotado de la IA.
3. **Especificación:** funciones, entradas, salidas, criterios de aceptación y casos límite.
4. **La pieza de IA:** tecnología, elección y comportamiento frente a errores o cuotas.
5. **Proceso con IA:** AGENTS.md/harness, prompts clave, trabajo delegado a la IA y controles humanos.
6. **Prueba y mejora:** persona que probó, qué ocurrió y modificación aplicada. Prueba de compañero/feedback, solo si se realizó.
7. **Pitch escrito:** exactamente cinco frases (problema, solución, IA, prueba y siguiente paso).
8. **Capturas:** cuatro evidencias reales comentadas: funcionamiento, error/caso límite, proceso con IA y prueba.

## Rúbrica (peso sobre la actividad)

| Criterio | Peso |
|---|---:|
| Problema y usuario | 10 % |
| Especificación y prompting | 10 % |
| App desplegada y funcional | 25 % |
| Integración de la IA | 20 % |
| Proceso con IA y harness | 15 % |
| Prueba y mejora | 10 % |
| README y pitch escrito | 10 % |
| **Total** | **100 %** |

Niveles: Básico (4), Intermedio (6), Avanzado (8), Experto (10); 0 si se omite. Si la aplicación no abre al corregirse, la nota máxima es 3. Si la API key aparece en el código/repositorio, la nota de integración IA queda en Básico. Comprobar Space en incógnito y los secretos antes de entregar.

## Cronograma indicado en el HTML

- Semana 1 (07/10/2026): problema, persona usuaria y primer despliegue.
- Semana 2 (14/10/2026): especificación y versión 0; ficha voluntaria de cinco líneas recomendada antes de 20/10.
- Semana 3 (21/10/2026): integración de IA y prueba entre compañeros.
- Semana 4 (28/10/2026): entrega final, README y pitch.
- Cierre: 02/11/2026. La actividad individual no requiere vídeo.

## Implementación en el Space

`app.py` → panel **Proyecto** → acordeón **Entregables académicos · Módulo 1**. El editor presenta ocho textos precargados basados en el código real, no en datos personales. Nombre del estudiante y cuatro capturas se completan manualmente. Los botones **Actualizar vista previa** y **Generar Word (.docx)** usan `inbody_mvp/module1_deliverable.py`. El DOCX contiene los ocho apartados, portada, cuatro capturas si se adjuntan y notas de **pendiente de adjuntar** en su ausencia.

**Privacidad:** los borradores viven en controles Gradio de la sesión, los archivos Word se generan temporalmente para descarga, sin SQL ni llamada a Gemini. Los cambios escritos no persisten entre sesiones. No se publica la plantilla Blackboard porque no se aportó; la estructura reproduce los requisitos de la consigna HTML, no su estilo visual original.

**Pruebas:** `tests/test_module1_deliverable.py` comprueba ocho apartados, cinco frases, Word válido, cuatro imágenes, validación de archivos y conexión UI/deploy. Pendiente la prueba visual real en el Space después de fusionar/desplegar.
