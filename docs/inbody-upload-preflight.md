# Comprobación de archivo repetido antes de extraer (2026-11-03)

El archivo se verifica al **seleccionarlo**, antes de habilitar
«Extraer mediciones con IA». Una sesión privada autorizada consulta
`public.hj_audit_filename_processed(:filename)` mediante SQL parametrizado
en Neon. Esta comprobación **no utiliza Gemini ni consume tokens**.
El botón de extracción permanece inactivo mientras se verifica.

- **Duplicado confirmado:** la interfaz muestra aviso y deshabilita
  «Extraer»; no avanza al paso 2. La función de extracción en el
  servidor repite la consulta inmediatamente antes de llamar a Gemini
  y bloquea incluso una solicitud con botón alterado o estado obsoleto.
- **Nombre nuevo:** habilita Extraer y permite seguir con el flujo.
- **No verificado:** si la sesión no puede leer el registro privado o
  la base no está disponible, se explica que no es posible garantizar
  que sea nuevo. Se permite extracción voluntaria para no romper
  el uso sin base de datos; puede gastar tokens si ya existe.
- **Sin archivo válido:** Extraer permanece deshabilitado.

La selección se vincula al hash SHA-256 **calculado en el servidor**
de los bytes cargados; el hash y los bytes no se envían en la
consulta de nombre. La función actual detecta **coincidencias de nombre**,
no un fichero renombrado con contenido idéntico: para esto último
haría falta una consulta de hash privada y autorizada en una migración
posterior. El guardado final mantiene su propia detección de duplicados.

Pruebas sintéticas comprueban todos los estados, vínculo a bytes,
protección de privacidad y orden de callbacks. Requiere verificar
CI y probar la interfaz de Hugging Face tras fusión/despliegue.
