# AGENTS.md · Health Journey

## Qué es este proyecto

Health Journey es una plataforma modular para consolidar información personal de fitness y, en fases posteriores, documentos clínicos procedentes de aplicaciones que no comparten datos y de reportes PDF, PNG y JPG. La primera entrega es **InBody Hub**, enfocada en reunir evaluaciones de composición corporal de múltiples establecimientos y equipos en un historial confiable por persona.

## Hoja de ruta y alcance

1. **Fase 1 — InBody Hub:** captura, extracción, revisión, normalización y consolidación de reportes InBody. El ejemplo de 5 pruebas de una tienda y 6 de otra debe terminar en un historial unificado, sin duplicar registros ni perder fuentes.
2. **Fase 2 — Training + Nutrition:** unificar registros de entrenamiento (ejercicios, series, repeticiones, cargas y frecuencia) y macronutrientes (proteínas, carbohidratos, grasas y calorías); interpretar tendencias de progreso y hábitos.
3. **Fase 3 — Medical Hub:** integrar exámenes y resultados clínicos con privacidad reforzada y validación; no ofrecer diagnósticos.
4. **Capacidad transversal — asistente virtual:** habilitar, progresivamente, seguimiento de objetivos, hábitos y entrenamiento mediante datos verificables de los módulos.

**Regla de alcance:** no implementar fases 2 o 3 como parte del hito de la semana 2. Mantener como máximo tres funcionalidades principales del MVP, descritas en `especificacion.md`.

## Cómo está hecho (estado verificado en la rama main al 14/10/2026)

- **Python / interfaz actual:** Gradio en `app.py`. La interfaz tiene pestañas InBody Hub y Proyecto.
- **Extracción actual:** EasyOCR (es/en) con `spaces.GPU` para Hugging Face ZeroGPU y CPU en local cuando no hay CUDA. El usuario sube **una imagen** y recibe **texto no estructurado**; la extracción no persiste datos.
- **Documentación visible en la app:** la pestaña Proyecto lee `README.md` y omite la cabecera YAML del Space.
- **Dependencias:** `requirements.txt`.
- **Arquitectura prevista, todavía no desplegada:** React/TypeScript, FastAPI/Pydantic, PostgreSQL (SQLAlchemy/Alembic); desarrollo local, QA aislado y producción separada.
- **IA prevista:** API multimodal de Gemini para interpretar documentos de formatos variables. **No está conectada al MVP actual**. No presentarla como funcionalidad existente.

Documentos de referencia: `README.md` (visión, fases, estado), `especificacion.md` (contrato funcional y pruebas), `docs/hito-semana-2.md` (ficha académica).

## Reglas del agente

- Antes de modificar código, leer `README.md` y `especificacion.md`. Explicar el alcance del cambio y no agregar funcionalidades fuera de fase sin pedir confirmación.
- Hacer cambios pequeños y comprobables; preservar comportamiento existente. Al terminar, informar archivos, motivo y pruebas.
- **No cambiar arquitectura ni modelo de IA sin autorización.** No desplegar, hacer merge ni push a producción o a `main` sin revisión del usuario.
- Preservar el frontmatter YAML inicial de `README.md`: Hugging Face lo requiere para arrancar la app.
- No introducir datos personales de salud reales, credenciales, PDFs identificables ni nombres de pacientes en ejemplos, logs o pruebas. Usar datos sintéticos/anonimizados.
- Guardar cualquier `GEMINI_API_KEY` u otras credenciales solo en secretos/variables de entorno. Nunca en GitHub ni en un chat.
- Para documentos: distinguir PDF de texto de PDF escaneado; un OCR de imagen no demuestra que PDF ya funciona.
- Para mediciones: jamás inventar valores, fechas o unidades. Los campos ilegibles se dejan vacíos y requieren revisión humana. No reemplazar ausentes por cero.
- Mantener el identificador de persona separado del de examen, almacenar procedencia y modelo del equipo por examen y verificar duplicados. No mezclar series de personas diferentes.
- Marcar cambios de equipo, unidad, definición o método cuando afecten comparaciones entre pruebas; no asumir equivalencia sin validación.
- Validar entradas, controlar tamaños de archivo y devolver errores en español sin exponer secretos ni trazas internas.
- Para futuras funciones de IA, manejar errores de red, cuotas y formato de respuesta con `try/except` y mensajes claros; validar esquemas antes de persistir.
- En la fase clínica, no crear diagnósticos, recetas, cambios de medicación ni afirmaciones de certeza clínica. Asegurar privacidad, acceso autorizado y revisión de la información.
- Si añades una biblioteca, actualizar `requirements.txt` y documentar por qué es necesaria.

## Cómo comprobar que funciona

### Versión 0 (actual)

1. Ejecutar `pip install -r requirements.txt` y `python app.py` en un entorno apropiado.
2. Abrir `http://localhost:7860` o el Space de QA cuando esté operativo.
3. Probar subida de una imagen sintética legible → aparece texto OCR editable.
4. Probar imagen ausente → mensaje claro solicitando cargar una imagen.
5. Probar imagen que exceda 20 millones de píxeles → rechazo con mensaje claro.
6. Abrir pestaña Proyecto → se muestra el README, sin la cabecera YAML.

Estas son expectativas verificables desde el código, **no una declaración de pruebas ejecutadas**.

### Fase 1 posterior

- Validar PDF con texto y PDF escaneado, PNG/JPG, campos ilegibles, duplicados, 5+6 exámenes de dos fuentes, cambios de modelo y errores de cuota.
- Separar pruebas unitarias de extracción, normalización, reglas de negocio, persistencia y UI.
- No almacenar datos dudosos sin confirmación. Verificar los casos de `especificacion.md`.

## Qué no hacer

- No afirmar que los módulos Training, Nutrition y Medical ya funcionan.
- No confundir extracción OCR de texto con extracción validada de mediciones InBody.
- No borrar ni sustituir partes del README sin mantener el contenido existente y la configuración de Hugging Face.
- No usar datos sensibles reales ni servicios de producción para las pruebas del reto.
