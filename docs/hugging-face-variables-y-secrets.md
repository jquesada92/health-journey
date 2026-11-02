# Hugging Face Spaces — Variables y Secrets de Health Journey


## Inicio de sesión propio `obs-master-demo`

La aplicación puede exigir un login general de Gradio, sin crear una
cuenta adicional de Hugging Face. La cuenta de aplicación
`obs-master-demo` se almacena en **Neon**, en la tabla privada
`hj_app_accounts`, con hash PBKDF2-SHA256, contraseña de alta entropía
y bloqueo de 15 minutos tras cinco intentos erróneos.
La migración `migrations/006_app_master_demo_account.sql` crea
únicamente la tabla; el registro se aprovisiona de forma privada,
**nunca en el repositorio**.

Para activarlo en Hugging Face:

1. Aplicar la migración 006 en Neon.
2. Aprovisionar la cuenta `obs-master-demo` con hash seguro.
3. Añadir la Variable pública `ENABLE_APP_PASSWORD_LOGIN=1` en
   Settings → Variables and secrets. Mantener `DATABASE_URL` como Secret,
   apuntando a un rol privado con permiso sobre `hj_app_accounts`.
4. Reiniciar el Space. Gradio muestra la pantalla de inicio de sesión
   antes de cualquier pestaña; el usuario accede con
   `obs-master-demo` y la contraseña inicial entregada por canal privado.
5. Rotar la contraseña mediante el procedimiento administrativo privado, fuera de la interfaz principal. El login se mantiene activo.

   archivos, capturas o logs.

Con el login habilitado, **todos los módulos** quedan detrás de la
pantalla de autenticación: carga, extracción Gemini, revisión,
consentimientos, guardado, Dashboard, historial y diagnóstico.
Los módulos siguen sujetos a sus dependencias normales:
`GEMINI_API_KEY`, `DEMO_DATABASE_URL`, `ENABLE_ANONYMOUS_DEMO`,
`PUBLIC_DATABASE_URL` y vistas SQL. El login no crea datos que no
existan ni autoriza la publicación de exámenes privados.

La lectura de Neon acepta el usuario validado por el middleware de
Gradio mediante `gr.Request.username`. No se acepta un username
enviado por textbox, query string ni un header inventado por el
cliente. Las cuentas OAuth de Hugging Face siguen conservando su
comprobación de `HF_ALLOWED_USERS` cuando el modo de password está
desactivado. Activar el modo login hace que el Space requiera una
sesión para toda la UI; no habilita acceso anónimo al Dashboard.

La protección integrada de Gradio es adecuada para una demostración
controlada, pero **no sustituye** MFA, mitigación de abuso en ingress
y controles de acceso a nivel de fila en un producto multiusuario.
En un Space público, no subir reportes identificables sin tener
un entorno y una política de privacidad apropiados.


Esta guía describe **las cinco Variables y los cuatro Secrets** mostrados en
`jaqo/health-journey` (Settings → Variables and secrets). Los nombres fueron
contrastados con el código de `main`; la captura **no muestra sus valores
actuales**. No asumir que una opción está activada solo porque exista.

## Diferencia entre Variable y Secret

- **Variable (Public)**: parámetro de configuración no confidencial, como
  `0` / `1` o el nombre del modelo. Su valor puede estar expuesto en los
  metadatos del Space. **Nunca colocar aquí passwords ni claves API.**
- **Secret (Private)**: credencial que se inyecta como variable de entorno
  del contenedor. No se debe imprimir, guardar en logs, GitHub, PRs ni ejemplos
  reales. Una clave en un Secret **no convierte un Space público en privado**.

## Variables (Public)

| Variable | Valores / ejemplo | Función real en el código | Cuándo habilitar |
|---|---|---|---|
| `ENABLE_PERSISTENCE` | `0` o `1` | Habilita el flujo **privado heredado** de lectura y escritura a Neon mediante `DATABASE_URL`, sujeto a `HF_ALLOWED_USERS` y OAuth cuando corre en Spaces. **No** controla el guardado de auditoría Gemini mediante la conexión demo. | `0` para QA pública; `1` solo cuando el flujo privado esté configurado y autorizado. |
| `HF_ALLOWED_USERS` | `usuario_hf` o `usuario1,usuario2` | Lista de usuarios de **Hugging Face** permitidos para operaciones privadas de `inbody_mvp/storage.py`. El username debe coincidir con el perfil OAuth; no son IDs InBody ni roles PostgreSQL. | Configurar únicamente con los usuarios que deben ver o administrar historial privado. No habilita por sí solo la escritura. |
| `ENABLE_PUBLIC_DASHBOARD` | `0` o `1` | Habilita consultas de dashboard desde **`PUBLIC_DATABASE_URL`**: vistas públicas expresamente aprobadas, no tablas privadas. Requiere tener configurado el Secret lector. | `1` si deseas mostrar resultados aprobados para publicación; `0` para ocultar/desactivar la consulta. |
| `ENABLE_ANONYMOUS_DEMO` | `0` o `1` | **Único flag compartido** para el demo anónimo (`hj_submit_demo_report`) y el envío de auditorías Gemini revisadas (`hj_submit_reviewed_audit`) sin login, usando `DEMO_DATABASE_URL`. En ambos casos el botón/formulario aplica sus validaciones y consentimientos. | `1` solo con el Secret restringido, procedimientos SQL necesarios y controles apropiados; `0` impide las escrituras anónimas. |
| `GEMINI_MODEL` | Nombre de modelo, p. ej. `gemini-3.8-flash` | Modelo principal de Google Gemini para extracción estructurada de PDF/imágenes en `inbody_mvp/gemini_review.py`. Si la variable no está definida, el código usa el modelo predeterminado de esa versión. | Debe corresponder a un modelo disponible para la API key. Un valor inválido o sin acceso puede generar HTTP 404. |

### Consideraciones de las variables

**`ENABLE_PERSISTENCE` y `ENABLE_ANONYMOUS_DEMO` no son intercambiables.**
El primero protege el camino privado histórico; el segundo habilita operaciones
sin login con un rol SQL que solo debe ejecutar funciones controladas.
`HF_ALLOWED_USERS` **no restringe** el formulario anónimo de Gemini ni el
dashboard público: estos tienen permisos y consentimientos independientes.

El dashboard público no publica automáticamente el contenido de auditorías
Gemini. Autorizar almacenamiento **no equivale** a autorizar publicación.

**Interacción importante de la interfaz:** cuando `ENABLE_ANONYMOUS_DEMO=1`,
la pestaña «Historial en Neon» deshabilita sus botones de consulta privada.
Por eso no es posible habilitar simultáneamente en esa interfaz el guardado
anónimo de auditorías y la lectura privada del historial solo cambiando
`ENABLE_PERSISTENCE`. Son dos modos distintos de operación del Space actual.

## Secrets (Private)

| Secret | Formato esperado | Propósito / rol PostgreSQL | Restricciones |
|---|---|---|---|
| `DATABASE_URL` | URL PostgreSQL a Neon, con `sslmode=require` | Conexión **privada** para historiales y registros heredados mediante `inbody_mvp/storage.py`. Debe usarse con OAuth, `HF_ALLOWED_USERS` y `ENABLE_PERSISTENCE=1`. | No utilizar la cuenta administradora ni compartirlo con procedimientos anónimos. No sustituye a `DEMO_DATABASE_URL`. |
| `PUBLIC_DATABASE_URL` | URL PostgreSQL a Neon, con `sslmode=require` | Rol de **solo lectura** (por ejemplo `health_journey_public`) para vistas autorizadas del dashboard. Se usa si `ENABLE_PUBLIC_DASHBOARD=1`. | No otorgar SELECT directo a `hj_persons`, `hj_extraction_audits`, identificadores originales ni JSON bruto. |
| `DEMO_DATABASE_URL` | URL PostgreSQL con `sslmode=require` y usuario exacto `health_journey_demo_writer` | Rol limitado a ejecutar procedimientos de escritura controlados. Lo usan el demo sin login y las auditorías Gemini revisadas cuando `ENABLE_ANONYMOUS_DEMO=1`. | No admite `DATABASE_URL` de administrador. Las funciones requeridas deben existir en Neon; la consulta privada sigue prohibida para este rol. |
| `GEMINI_API_KEY` | Clave API de Google AI Studio / Gemini | Autentica peticiones de extracción y la consulta de modelos disponibles. El documento se envía a Google **solo después del consentimiento de envío**. | No mostrar ni registrar la clave. Revisar permisos, cuota, modelo disponible y condiciones aplicables a datos de salud. |

**Ejemplo de formato** (solo placeholders, nunca credenciales reales):

```dotenv
# Variables (Public)
ENABLE_PERSISTENCE=0
HF_ALLOWED_USERS=usuario_hf_autorizado
ENABLE_PUBLIC_DASHBOARD=1
ENABLE_ANONYMOUS_DEMO=0
GEMINI_MODEL=gemini-3.8-flash

# Secrets (Private): valores redactados
DATABASE_URL=postgresql://ROL_PRIVADO:REDACTED@HOST/health_journey?sslmode=require
PUBLIC_DATABASE_URL=postgresql://health_journey_public:REDACTED@HOST/health_journey?sslmode=require
DEMO_DATABASE_URL=postgresql://health_journey_demo_writer:REDACTED@HOST/health_journey?sslmode=require
GEMINI_API_KEY=REDACTED
```

Los valores del ejemplo son **ilustrativos**; no describen los valores
reales de tu Space ni implican que debas activar la escritura anónima.
En PostgreSQL, las contraseñas con caracteres especiales deben codificarse
correctamente para una URL.

## Dependencias y rutas de funcionamiento

| Necesidad | Variables | Secrets | Autorización adicional |
|---|---|---|---|
| Previsualizar PDF/imagen | Ninguna | Ninguno | Subida local a Gradio; **no** envía a Gemini todavía. En Space público usar solo archivos anonimizados/sintéticos. |
| Extraer mediciones con Gemini | `GEMINI_MODEL` (opcional) | `GEMINI_API_KEY` | Consentimiento independiente para enviar documento a Google. |
| Guardar mediciones revisadas sin login | `ENABLE_ANONYMOUS_DEMO=1` | `DEMO_DATABASE_URL` | Consentimiento Neon, revisión completa, rol `health_journey_demo_writer` y función SQL `hj_submit_reviewed_audit(jsonb)` (migración 005). |
| Guardar demo con publicación opcional | `ENABLE_ANONYMOUS_DEMO=1` | `DEMO_DATABASE_URL` | Validaciones/consentimientos separados y función `hj_submit_demo_report` (migración demo 004). |
| Consultar dashboard público | `ENABLE_PUBLIC_DASHBOARD=1` | `PUBLIC_DATABASE_URL` | Solo vistas publicadas/autorizadas; consentimiento de almacenamiento no publica auditorías. |
| Consultar historial privado | `ENABLE_PERSISTENCE=1`, `HF_ALLOWED_USERS` y `ENABLE_ANONYMOUS_DEMO=0` | `DATABASE_URL` | Sesión OAuth de Hugging Face autorizada. En modo demo la interfaz actual deshabilita estos controles. |
| Consultar auditorías privadas por ID del InBody | `ENABLE_PERSISTENCE=1`, `HF_ALLOWED_USERS` y `ENABLE_ANONYMOUS_DEMO=0` | `DATABASE_URL` | OAuth y migración 005; normaliza `88571257` / `8-857-1257`, muestra un alias aleatorio persistente, no la cédula ni el archivo. |

## Variables complementarias (no aparecen en la captura)

- `GEMINI_FALLBACK_MODEL` (Variable opcional): modelo alternativo cuando el
  principal termina con HTTP 503. Si no se define, el código usa
  `gemini-3.5-flash-lite`; `off` desactiva el fallback. Puede requerir cuota
  adicional y no garantiza acceso al modelo.
- `SPACE_ID` / `SPACE_HOST`: contexto proporcionado por el hosting para el
  comportamiento de Spaces y enlaces OAuth. No deben confundirse con
  `HF_ALLOWED_USERS`.
- **No configurar `ENABLE_ANONYMOUS_AUDIT`**: se retiró; la bandera actual
  es `ENABLE_ANONYMOUS_DEMO`.

## Verificación de Neon y solución de problemas

La migración 005 fue **aplicada y verificada** en Neon
`health_journey`, rama `main`, el **1 de noviembre de 2026**, tras
validación en una rama temporal con documentos e IDs sintéticos:

- `hj_submit_demo_report`: **instalada** (migración 004).
- `hj_submit_reviewed_audit(jsonb)`: **instalada** (migración 005).
- `hj_person_aliases`: **instalada**, alias UUID aleatorio por ID normalizado.
- `hj_audit_reviewed_private`: **instalada**, lectura solo para roles privados.

Se confirmó que el rol `health_journey_demo_writer` puede ejecutar
ambas funciones sin permisos SELECT sobre IDs ni auditorías privadas;
`health_journey_public` tampoco puede leer la vista de auditoría.
La instalación SQL **no garantiza** que el flujo de Hugging Face ya
funcione end-to-end: se necesitan los valores correctos de las Variables,
los Secrets, los consentimientos y la validación de la aplicación.
No es necesario repetir la migración si estos objetos siguen presentes.

Síntomas típicos:

- **Botón «Guardar auditoría» deshabilitado:** revisar
  `ENABLE_ANONYMOUS_DEMO=1` y el Secret `DEMO_DATABASE_URL` con usuario
  `health_journey_demo_writer` y `sslmode=require`.
- **Botón activo pero el guardado falla:** revisar que migración 005
  haya creado la función y que el rol tenga EXECUTE, y comprobar si el
  documento se registró anteriormente.
- **Dashboard público vacío:** verificar `ENABLE_PUBLIC_DASHBOARD`,
  `PUBLIC_DATABASE_URL`, permisos de vistas y que existan datos
  explícitamente aprobados para publicación.
- **Error 401/403/404/429/503 en Gemini:** verificar Secret de API,
  permisos del modelo, límites y disponibilidad; no exponer el mensaje
  bruto de error ni el documento en logs.
- **Historial privado inaccesible:** verificar `ENABLE_PERSISTENCE`,
  `DATABASE_URL`, `HF_ALLOWED_USERS` y sesión OAuth. El ID real
  del InBody no debe figurar en tablas/gráficas consultables.

## Controles mínimos de privacidad

1. **Consentimiento para Gemini ≠ consentimiento para Neon ≠ autorización
   de publicación.** Cada propósito requiere una decisión clara.
2. El ID de reporte (`88571257`, `8-857-1257`) es información personal.
   Las dos variantes se vinculan internamente, pero el dashboard de auditoría
   privado muestra únicamente un alias aleatorio y no el identificador real.
3. **Alias no significa anonimato irreversible**: fechas, valores y tendencias
   individuales pueden permitir reidentificación. El dashboard público no debe
   exponer filas de auditoría individuales solo porque estén guardadas.
4. Un Space público y el caché de archivos de Gradio pueden exponer
   documentos. Para resultados de salud identificables, usar un entorno
   privado con acceso controlado, minimización de datos y política de
   retención adecuada.
5. Cambiar una Variable no cambia automáticamente permisos SQL, funciones,
   secretos ni autorizaciones de usuarios.

**Dónde se usan en el código:** `inbody_mvp/storage.py`,
`inbody_mvp/demo_storage.py`, `inbody_mvp/public_dashboard.py`,
`inbody_mvp/gemini_review.py` y `app.py`.


## Selector de modelos Gemini Flash (Free Tier)

En **InBody Upload** hay un menú desplegable de modelos
adecuados para leer el PDF/imagen y entregar las mediciones como JSON.
La aplicación consulta `client.models.list()` con la clave
`GEMINI_API_KEY` guardada como Secret; no manda ningún documento al
consultar los modelos. Interseca el resultado con esta lista de
**modelos cuyo nivel gratuito estándar está documentado por Google**
(consultada en noviembre de 2026):

- `gemini-3.8-flash`: recomendado para tablas y relaciones espaciales complejas.
- `gemini-3.6-flash`: alternativa multimodal.
- `gemini-3.5-flash-lite`: alternativa rápida y ligera.
- `gemini-3.1-flash-lite`: alternativa ligera.
- `gemini-2.5-flash` y `gemini-2.5-flash-lite`: modelos
  heredados; Google puede limitar su disponibilidad a proyectos con uso previo.

El menú solo enseña la intersección con los modelos **accesibles para
la API key**, y se actualiza automáticamente al entrar o con
«Actualizar modelos disponibles». Se prioriza el valor de
`GEMINI_MODEL` si aparece entre los accesibles; si no, se propone
`gemini-3.8-flash` cuando está disponible. Elegir un modelo cambia
solo la **siguiente extracción**; no modifica Secrets ni las
Variables del Space. El modelo efectivo (incluido el fallback 503)
queda registrado en el snapshot de auditoría. No se permite elegir un
modelo Pro, TTS, Live o de generación de imágenes.

**Advertencia:** que el proveedor anuncie **Free Tier** y liste un
modelo no prueba que el proyecto sea gratuito, que conserve cuota ni
que la facturación esté desactivada. En proyectos pagos puede haber
cargos; comprobar el nivel y límites reales en Google AI Studio.
Google también indica que los datos enviados en Free Tier pueden
usarse para mejorar sus productos. No subir resultados médicos
identificables a ese nivel sin revisar sus condiciones y consentimiento.

Fuente: https://ai.google.dev/gemini-api/docs/pricing y
https://ai.google.dev/gemini-api/docs/models

## Limpieza de herramientas del inicio

Se eliminaron de la UI principal los acordeones «Seguridad de la
cuenta (cambiar contraseña)» y «Diagnóstico ZeroGPU (opcional)».
**El inicio de sesión sigue habilitado**; el cambio de contraseña se
gestiona administrativamente y no aparece en el dashboard. Dado que
el Space utiliza hardware ZeroGPU, permanece un handler técnico
`@spaces.GPU` **invisible y sin endpoint público**, solo para
satisfacer el requisito de arranque; la extracción Gemini utiliza
la API de Google y no solicita GPU local.
