# Selector de modelo integrado en el chat fitness

**Cambio propuesto (3 de noviembre de 2026)**

En el módulo «Chat con el asistente fitness», el selector de modelos
**Gemini Flash** aparece dentro de la burbuja de redacción, en una barra
inferior junto al botón «Enviar» y al control «↻» para actualizar la lista.
El campo de texto ocupa la zona superior de la misma burbuja.
La presentación adapta dimensiones y separación para pantallas móviles.

El modelo seleccionado se utiliza para la **pregunta actual**. Al pulsar
Enter o Enviar, se guarda el modelo en el estado de sesión
`coach_pending_model`; el campo, el selector, el control de refresco,
Enviar y Limpiar conversación quedan temporalmente inactivos durante la
solicitud para impedir que una selección posterior cambie la petición
pendiente. Cuando llega la respuesta o falla la API, los controles
se reactivan y se conserva el hilo.

Actualizar modelos filtra los resultados de Google por la lista permitida
del **chat** y conserva el modelo activo si continúa disponible. Si deja
de estarlo, elige uno permitido. El selector de la extracción InBody
sigue siendo independiente.

**Límites y seguridad:** el cambio no modifica prompts, consentimiento,
base Neon, permisos ni extracción. Google Gemini sigue siendo el proveedor.
Las opciones en la interfaz no garantizan cuotas gratuitas; la clave del
proyecto determina el acceso y la facturación. El historial del chat
continúa solo en la sesión Gradio.

**Validación requerida:** revisar CI de
`tests/test_coach_chat_ui.py`; probar manualmente en Hugging Face Space
(escritorio y móvil) enviar dos o más preguntas, cambiar de modelo entre
ellas, actualizar la lista y simular un error de API. Esta nota no
afirma despliegue ni pruebas end-to-end ya realizadas.
