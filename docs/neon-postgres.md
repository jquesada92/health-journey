# Neon PostgreSQL + idioma de reportes — InBody Hub

## Estado

- Proyecto Neon creado: **health-journey** (ID: `autumn-pond-85488960`).
- Base PostgreSQL: `health_journey`, PostgreSQL 17, rama `main`, región `aws-us-east-1`.
- Se crearon y comprobaron las tablas `hj_persons`, `hj_exams`, `hj_measurements`, `hj_measurement_catalog` y la vista `hj_measurements_long`.
- El esquema reproducible está versionado en [`db/schema.sql`](../db/schema.sql).
- El almacenamiento del archivo original **no está implementado**. Solo se registra su hash SHA-256, no el PDF/JPG/PNG.
- La base está inicialmente vacía; nunca cargar documentos reales de personas al Space público sin controles de acceso.

## Idioma ES/EN

Se añade `idioma_reporte` como atributo de **examen**, no como nueva columna por medición. Valores permitidos:

- `ES`: evidencia suficiente de encabezados y etiquetas españolas.
- `EN`: evidencia suficiente de encabezados y etiquetas inglesas.
- `UNKNOWN`: evidencia insuficiente, mezcla indistinguible u OCR deficiente.

El motor `inbody_mvp/language.py` clasifica el texto por encabezados y frases de referencia. En `app.py` se puede corregir el idioma manualmente antes de guardar. **No se modifica la etiqueta original**, y el identificador normalizado de la variable permanece independiente del idioma. Así se podrá ampliar un catálogo `display_label_es` / `display_label_en` sin migraciones por cada métrica. Los valores `UNKNOWN` requieren revisión: no asumir idioma.

## Estructura del modelo

- `hj_persons`: identificador del reporte (sin afirmar que es una cédula verificada), espacio de identificadores, ID interno UUID.
- `hj_exams`: persona, máquina/modelo, fecha y hora **tal como se reporta**, zona horaria solo cuando se conozca, edad y origen, idioma, SHA-256 de documento.
- `hj_measurements`: una fila por medición: nombre normalizado, etiqueta original, categoría, dimensión, segmento, frecuencia kHz, unidad, valor, página y método de extracción.
- `hj_measurement_catalog`: catálogo bilingüe extensible para correspondencias y criterios de comparabilidad. **Aún no está poblado automáticamente**.
- `hj_measurements_long`: vista SQL con las siete columnas solicitadas: `id_persona`, `modelo_inbody`, `timestamp`, `variable_medida`, `unidad_medida`, `valor_medida`, `edad`.

En este MVP el `timestamp` es local y puede no tener zona horaria; no se inventa un offset. Los porcentajes de referencia no se equiparan con porcentajes corporales, y el ángulo de fase conserva el segmento y frecuencia cuando el reporte los indica.

## Conectar la aplicación en local

1. Abre [Neon Console](https://console.neon.tech), selecciona **health-journey** y pulsa **Connect**.
2. Selecciona `main`, base `health_journey` y el rol correspondiente. Copia el connection string, con TLS `sslmode=require`. La URL contiene una contraseña: **no la compartas en chats ni la subas a GitHub**.
3. En tu directorio local `health-journey`, crea `.env` a partir de `.env.example`. Actualiza `DATABASE_URL` con la URL privada de Neon y cambia `ENABLE_PERSISTENCE=1`.
4. Instala dependencias e inicia Gradio localmente:

```bash
python -m pip install -r requirements.txt
python app.py
```

5. Abre **http://127.0.0.1:7860**, carga un documento de prueba, revisa todos los datos y pulsa **Confirmar y guardar en PostgreSQL**. El botón solo aparece en ejecución local con ambas variables configuradas.

**No se habilita persistencia en Hugging Face Spaces** cuando existe `SPACE_ID`. En ese caso, la app conserva carga, OCR, revisión y CSV, pero no ofrece acceso a Neon. Para habilitar datos reales en un servidor futuro hacen falta autenticación, autorización por persona, políticas de retención, almacenamiento seguro de archivos originales y controles de auditoría. No introducir `DATABASE_URL` como secreto del Space público durante este MVP.

## Validación y duplicados

- La aplicación no guarda automáticamente tras OCR: el usuario debe corregir y confirmar.
- Identificador, timestamp y al menos una medición numérica validada son obligatorios.
- Valores ilegibles o sin respaldo se rechazan o se retiran antes de confirmar.
- El guardado es transaccional con SQLAlchemy; `source_sha256` único impide duplicar un mismo documento.
- El mismo identificador de reporte en distintos establecimientos **no prueba por sí solo** que se trate de una única persona. La reconciliación de identidades es posterior.
- Las pruebas automatizadas usan únicamente datos ficticios y no requieren Neon.

## Consultar resultados

En el editor SQL de Neon:

```sql
SELECT *
FROM hj_measurements_long
ORDER BY "timestamp" DESC, variable_medida
LIMIT 100;
```

Para revisar idiomas y segmentos:

```sql
SELECT e.idioma_reporte, e.modelo_inbody, e.exam_timestamp,
       m.variable_medida, m.segmento, m.frecuencia_khz,
       m.unidad_medida, m.valor_medida
FROM hj_exams e
JOIN hj_measurements m ON e.exam_uuid=m.exam_uuid
ORDER BY e.exam_timestamp DESC, m.row_number
LIMIT 100;
```

La vista y las consultas no garantizan que las mediciones de distintos equipos sean comparables: el dashboard deberá respetar las definiciones, unidades y metodologías de cada modelo.

## Botón de guardado en Gradio / Hugging Face

En la pestaña **InBody Upload**, después de la tabla de revisión y del botón **Exportar borrador CSV**, aparece **Guardar examen confirmado en Neon**. El botón se muestra siempre, pero permanece **deshabilitado** hasta completar la configuración.

En **Hugging Face Space → Settings → Variables and secrets**, configura:

| Tipo | Nombre | Valor |
| --- | --- | --- |
| **Secret** | `DATABASE_URL` | Connection string del usuario restringido de Neon con `sslmode=require` |
| **Variable** | `ENABLE_PERSISTENCE` | `1` |
| **Variable** | `HF_ALLOWED_USERS` | Tu usuario Hugging Face exacto (o varios separados por coma) |

Después haz **Restart** o **Factory reboot** del Space y usa **Login** con una cuenta incluida en la lista. Si el botón sigue gris, revisa los nombres de las tres variables: se evalúan al arrancar la aplicación. No copies la URL privada en GitHub, README ni comentarios.

**Seguridad:** en el Space, las operaciones de OCR, consulta, exportación y guardado comprueban el usuario OAuth en el servidor cuando la persistencia está habilitada. La lista de usuarios es un control básico de MVP para un solo propietario, **no un sistema de autorización multiusuario**. Antes de manejar reportes personales, limita además la visibilidad del Space a privado, revisa la retención de archivos temporales y valida que el usuario PostgreSQL no herede permisos administrativos.

El botón solo confirma el guardado después de una transacción exitosa; no presupone que el rol tenga permiso de conexión ni que una credencial configurada sea válida. El estado real se comprueba ejecutando una inserción y consulta de prueba con datos sintéticos.


## Diagnóstico de autorización OAuth en Hugging Face

**Corrección de compatibilidad:** la clase de Gradio `OAuthProfile` expone `username` (identificador `jaqo`) y `name` (nombre para mostrar). **La allowlist `HF_ALLOWED_USERS` siempre debe compararse con `profile.username`**, nunca con el nombre visible. De otro modo una cuenta autenticada puede ser rechazada o un usuario con nombre visible coincidente puede obtener acceso indebido.

- En Spaces, `hf_oauth: true` debe constar en la cabecera del `README.md`.
- La dependencia `gradio[oauth]` instala los componentes adicionales requeridos para OAuth.
- Abre el Space, pulsa **Login** y autoriza el acceso; si hay problemas con la sesión dentro de la vista incrustada, abre el Space en una pestaña independiente.
- `HF_ALLOWED_USERS=jaqo` es una variable de entorno, no un secreto y no lleva `@`, nombre visible ni correo.
- La extracción y la exportación CSV **no dependen de la configuración de Neon**. Si `HF_ALLOWED_USERS` está definida dentro del Space, ambas operaciones exigen una sesión HF autorizada por tratarse de archivos potencialmente sensibles.
- Guardar y consultar Neon requieren adicionalmente `ENABLE_PERSISTENCE=1` y `DATABASE_URL`; cada operación comprueba la sesión.
- Si el Space no tiene allowlist, la extracción solo debe usarse con datos sintéticos o anonimizados; no constituye un entorno privado seguro.
- Nunca resuelvas el error deshabilitando las comprobaciones SQL o usando el rol administrador de Neon.

## Acceso opcional tras retirar el login del OCR

La carga, extracción OCR, revisión y exportación del CSV borrador **no solicitan inicio de sesión de Hugging Face**. El botón «Comprobar sesión de Hugging Face» y la ventana de acceso situada en la cabecera de la aplicación se han eliminado.

El inicio de sesión OAuth se conserva solamente para **guardar exámenes personales en Neon o consultar su historial privado**. Cuando la conexión privada está habilitada en un Space, el botón de acceso se encuentra en el acordeón cerrado «Acceso privado a Neon». El backend verifica `OAuthProfile.username` contra `HF_ALLOWED_USERS` en **cada** lectura y escritura; esconder un botón no concede permisos.

**Seguridad:** un Space público con OCR anónimo solo debe recibir archivos sintéticos o anonimizados **antes** de subirlos. El archivo fuente puede contener cédulas/nombres/fechas de nacimiento que el backend reciba aunque la interfaz oculte una columna. No utilizar este modo con informes identificables. Para documentos reales, mantener un entorno privado.
