# Health Journey — dashboard público y OCR en un mismo Space

**Estado:** decisión de interfaz consolidada el 31 de octubre de 2026.

## Diseño vigente

Un mismo `app.py` en Gradio ofrece estas pestañas y operaciones:

- **InBody Upload**: seleccionar JPG, PNG o PDF, ejecutar OCR, revisar candidatos y exportar CSV sin inicio de sesión.
- **Guardar en Neon e Historial en Neon**: requiere autenticación OAuth de Hugging Face **por operación**, con `HF_ALLOWED_USERS` y credenciales privadas.
- **Dashboard público**: consultar medidas previamente autorizadas mediante el rol PostgreSQL **solo lectura** `health_journey_public`. No se exige iniciar sesión.

La configuración `ENABLE_PUBLIC_DASHBOARD=1` habilita el dashboard público y **no deshabilita el selector de archivos, OCR, CSV ni los botones privados**. Si la conexión pública falta, el dashboard mostrará un estado no disponible; el OCR seguirá funcionando.

## Variables de un único Space

| Configuración | Tipo HF | Propósito |
| --- | --- | --- |
| `ENABLE_PUBLIC_DASHBOARD=1` | Variable | Activar las gráficas públicas |
| `PUBLIC_DATABASE_URL` | **Secret** | Conexión PostgreSQL con el rol `health_journey_public`: `SELECT` solo en vistas públicas |
| `ENABLE_PERSISTENCE=1` | Variable | Habilitar acciones privadas de Neon |
| `DATABASE_URL` | **Secret** | Conexión PostgreSQL con rol restringido `health_journey_runtime` para guardar y consultar |
| `HF_ALLOWED_USERS=jaqo` | Variable | Lista exacta de nombres de usuario HF autorizados para operaciones privadas |

**Nunca confundir las conexiones.** El lector público debe usar únicamente `PUBLIC_DATABASE_URL`. Los callbacks privados requieren autorización en servidor y usan únicamente `DATABASE_URL`. El dashboard jamás consulta ni devuelve `hj_persons` o la vista privada `hj_measurements_long`.

## Datos publicados

Hay dos vistas de PostgreSQL con propósito distinto:

- `hj_public_monthly_summary`: promedios por mes y cohorte, mínimo 5 personas distintas por grupo.
- `hj_public_person_series`: valores individuales **seudonimizados** para exámenes publicados voluntariamente. Usa un alias aleatorio y fecha de examen sin hora; no expone nombre, cédula/ID InBody, edad, DOB, nombre del archivo ni OCR.

La casilla **«Publicar las mediciones de este examen en mi dashboard público»** empieza desmarcada. Solo un guardado autorizado puede aprobar la publicación del examen. No se publica el historial completo automáticamente.

**Esto no garantiza anonimato irreversible:** fechas, valores y tendencias podrían permitir que alguien reconozca al propietario. La revocación auditable desde la interfaz está pendiente.

## Límite de privacidad del flujo sin login

El Space unificado permite **subir archivos sin OAuth**. En un Space público, Gradio recibe el JPG/PDF antes de que se ejecute el OCR. Eliminar el identificador del dataset público **no anonimiza el archivo que se acaba de subir**.

Por eso, antes de cargar un documento en una instancia pública:
1. Eliminar en la imagen/PDF original nombre, cédula, fecha de nacimiento y otros datos de identidad.
2. Revisar que no queden datos ocultos en metadatos o páginas adicionales.
3. Cargar únicamente archivos ya anonimizados o sintéticos.

Para archivos personales **sin anonimizar**, sigue siendo necesario un entorno privado o un control de acceso previo al upload. No existe garantía de confidencialidad de informes identificables en una interfaz pública anónima. Evitar exponer trazas del OCR o rutas originales en logs.

## Validaciones

1. Con `ENABLE_PUBLIC_DASHBOARD=1`, verificar que el selector JPG/PDF y el botón de extracción sigan activos.
2. Extraer un archivo sintético; confirmar que la extracción y descarga CSV funcionen sin OAuth/Neon.
3. Con `PUBLIC_DATABASE_URL` configurada, consultar un examen de prueba publicado y verificar el alias, los valores y la fecha sin hora.
4. Intentar consultar o guardar en Neon privado sin sesión OAuth: debe fallar.
5. Iniciar sesión con usuario autorizado y verificar que las operaciones privadas sí funcionen.
6. Auditar la cuenta pública PostgreSQL: permiso de `SELECT` únicamente sobre las vistas públicas.
7. Realizar prueba de extremo a extremo en Hugging Face, no confiar solo en CI.
