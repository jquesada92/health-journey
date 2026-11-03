## Prompts independientes y chat multi-turno (2026-11-03)

**Prompts:** `inbody_mvp/prompts/inbody_extraction.md` solo controla la
extracción y `inbody_mvp/prompts/fitness_coach.md` solo el chat.
Ambos se leen mediante `inbody_mvp/prompt_loader.py` desde el repositorio
y se incluyen en el despliegue Hugging Face. Para modificar la respuesta del
coach, editar el segundo archivo; para normalizar medidas InBody, editar
el primero. No introducir prompts largos incrustados en `.py`.

**Chat:** `inbody_mvp/chat_session.py` separa el historial visual de
los ocho mensajes recientes que Gemini recibe para dar contexto.
Al enviar, la burbuja del usuario se muestra antes de la llamada,
junto con un indicador temporal «Escribiendo…». Un único evento
`gr.on(triggers=[Enviar, Enter])` evita dos rutas independientes.
La respuesta o el fallo reemplaza el indicador, en orden, conservando
la pregunta. Limpiar conversación borra el estado visible de esa sesión.
El campo y los botones se bloquean mientras se espera al proveedor.
No se persiste el chat en Neon, ni se elimina el consentimiento firmado.

**Gemini:** la API usa `generate_content` con una lista de
`types.Content` alternando `user` y `model`; las instrucciones
del coach se envían como `system_instruction`. El contexto actual
contiene solo objetivos, restricciones y los resúmenes privados
autorizados. Las fuentes científicas no se descargan en tiempo real:
el prompt pide explicar la calidad de la evidencia y no fabricar
bibliografía. Ver `tests/test_coach_conversation.py` para una
conversación de varias preguntas con proveedor completamente simulado.

**Pendiente:** validación real en Space y móvil, con permiso y clave
propios, tras aprobación y despliegue del PR.

## Interfaz de conversación estilo WhatsApp (cambio del 2026-11-02)

El módulo Chat presenta un diseño de mensajería con cabecera
«Asistente fitness», burbujas de usuario a la derecha y Gemini a la
izquierda, colores suaves y caja de mensajes accesible en la parte
inferior. Se usa el **modo nativo `layout="bubble"` de Gradio 6**,
con CSS adicional limitado al componente y una media query móvil.

El desplegable **Modelo Gemini Flash para el chat** es local a esta
sección. No reemplaza ni sincroniza el selector independiente del
extractor InBody. Los objetivos, el ID de reporte, período y restricciones
se mantienen detrás de un acordeón que inicia cerrado, para priorizar
la conversación. El mensaje se envía mediante el botón Enviar o Enter;
se puede vaciar el hilo con Limpiar conversación. La cabecera es
texto HTML estático; no introduce un endpoint, JavaScript ni recursos
de terceros.

Los estilos y la cabecera están en
`inbody_mvp/coach_chat_ui.py`. Se incluyó el módulo en
`.github/workflows/deploy-huggingface.yml` y una prueba que instancia
el Chatbot con Gradio 6 en `tests/test_coach_chat_ui.py`.

**Estado:** pendiente de CI, revisión, merge y validación móvil en Space.
Las pruebas automatizadas no verifican píxeles ni tamaños reales en
iOS/Android. Esta UI no modifica los permisos, consultas SQL ni el
proveedor de IA Gemini.

# Chat con el asistente fitness · Health Journey

**Estado:** implementación propuesta en rama `feature/ai-coach-simplified-navigation-20261102`.
No fusionada, no desplegada, sin validación real con datos de salud.
El proyecto no ha modificado el esquema de Neon: esta versión solo consulta
datos autorizados y mantiene conversación y objetivos en la sesión Gradio.

## Experiencia de usuario

Después del login, la primera vista es **Proyecto**, con motivación,
propósito y arquitectura, y cuatro entradas únicas en el menú vertical:

1. Proyecto
2. Extractor de InBody
3. Captador de logs de entrenamiento
4. Chat con el asistente fitness

Sin pestañas horizontales ni overflow de tres puntos. Se retira el apartado
independiente **Historial**; se mantiene el progreso como acordeón dentro
de InBody. Se preservan los datos almacenados en Neon.

En el chat, el usuario introduce de forma opcional su ID de reporte InBody,
metas personales, restricciones y el periodo (30, 90, 180 o 365 días).
Puede cambiar su contexto y el modelo Flash, escribir preguntas y borrar el
chat de la sesión. Sin ID InBody, el análisis puede usar solo FitNotes.
No se guardan metas, restricciones ni mensajes en tablas PostgreSQL.

## Fuentes y reglas analíticas

- **InBody:** lectura protegida de `hj_audit_reviewed_private`, usando
  `load_reviewed_audit_history` y la autorización existente. Si no hay
  auditorías revisadas, se puede leer `hj_measurements` y
  `hj_exams` vía `load_measurement_history`. No se consultan valores
  históricos impresos en las imágenes/PDF.
- **Fitness:** la consulta parametrizada sobre `hj_training_sets`
  agrega por día, ejercicio y unidad del usuario autenticado
  (`_owner_key`). Se calcula recuento de series, reps, máximo peso
  no negativo y suma de cargas positivas por repeticiones.
- **Agrupación de InBody:** por sección, nombre de medición, unidad y
  modelo cuando existe. Precisión numérica basada en `Decimal`.
  Las auditorías existentes no ofrecen modelo de InBody de manera
  fiable: las tendencias deben advertir esta limitación y evitar
  atribuciones clínicas o equivalencias entre aparatos.
- **Comparabilidad:** ejercicios con distintos nombres o unidades se
  presentan por separado. Pesos negativos (asistidos) no contribuyen
  a volumen positivo. No inferir 1RM, fatiga, esfuerzo percibido,
  calorías, descanso, hipertrofia demostrada o causación a partir
  de las series registradas.
- **Ventana:** solo se consideran fechas dentro del periodo seleccionado;
  la consulta limita filas agregadas y número de series enviado a Gemini
  para evitar enviar tablas completas ni exceder recursos.

## Privacidad

Se introduce **un tercer consentimiento**, independiente de extraer
InBody con IA y de guardar en Neon. Debe concederse expresamente en la
pantalla previa al login o durante la sesión y se verifica mediante la
cookie de sesión firmada desde el backend. Marcar el checkbox de Gradio
sin sesión autorizada del servidor no permite enviar datos.

El chat **no** envía a Gemini ID de persona, alias privado, nombre de
archivo, PDF, JPG, CSV bruto, JSON de extracción, comentarios de
entrenamiento, credenciales SQL ni datos de otros usuarios. Envía
estadísticas agregadas sin esos identificadores junto con las metas,
restricciones y preguntas **que el usuario proporciona voluntariamente**.
Esto sigue siendo información de salud potencialmente sensible: utilizar
solo proyectos Gemini y espacios de ejecución con políticas de
privacidad aceptadas; no afirmar anonimización irreversible.

Las consultas Neon exigen autorización de la aplicación u OAuth
de Hugging Face y la allowlist donde corresponda. En MVP mono-usuario,
la lectura InBody se limita a un identificador elegido por el usuario,
pero no implementa aislamiento entre múltiples dueños InBody; para
multiusuario es obligatorio establecer una relación owner/persona
verificada y comprobaciones row-level antes de ofrecer esta función.
El FitNotes sí aplica `owner_key`.

El historial conversacional es temporal en `gr.Chatbot` y no se
persiste. `Limpiar conversación` borra el estado visible. No se
registran los prompts de salud en logs. No se añaden migraciones
ni permisos de roles para el chat.

## Modelos y coste

Se reutiliza `google-genai` y la lista controlada de modelos Gemini
Flash de `gemini_review.py`. El botón **Actualizar modelos** consulta
la lista asociada a la clave configurada. Disponibilidad, región,
precios y cuotas Free Tier dependen de Google y del proyecto. No
se garantiza gratuidad de una llamada ni se habilita facturación
por esta implementación. La IA se llama solo al enviar una pregunta.

## Instrucciones para el modelo

El prompt delimita un rol de analista/entrenador deportivo, exige citar
fechas, unidades y diferencias cuando existen y separar datos,
hipótesis y sugerencias. Debe informar ausencia de datos o limitaciones
de comparabilidad; no diagnosticar, prescribir fármacos ni recomendar
entrenar con signos de alarma. El contexto de base de datos se trata
como datos, nunca como instrucciones privilegiadas.

## Verificación y límites

- `tests/test_ai_coach.py`: precision decimal, fechas, unidades y
  modelos separados, consentimiento, ausencia de PII en contexto.
- `tests/test_sidebar_navigation.py`: exactamente cuatro rutas,
  panel Proyecto inicial y ausencia de `gr.Tab`.
- `tests/test_training_ui_contract.py` y
  `tests/test_progress_dashboard.py`: Training Hub y las gráficas
  conservadas dentro del InBody.
- `tests/test_prelogin_privacy.py`: consentimientos antes del login
  y protección de rutas privadas; incluye opt-in del chat.
- **CI verificado en PR #64 (commit `a6a37ee0`):** 305 pruebas,
  Ruff F821 y compilación Python aprobadas; harness verificado.
- La integración real en
  el Space, la selección del modelo y los permisos OAuth deben
  verificarse manualmente antes de fusionar o desplegar.
- Esta función **no es un dispositivo médico** ni una valoración
  de salud individual, y no implementa seguimiento en segundo plano.
