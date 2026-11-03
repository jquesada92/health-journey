# Guardado anónimo con consentimiento — demostración académica

> **Modo especial, no flujo principal (2026-11-03):** los permisos de demostración/publicación descritos aquí pertenecen a componentes condicionados por configuración. El usuario normal debe revisar tres consentimientos independientes **antes del login** en `/privacy`: extracción de InBody con Gemini, almacenamiento privado en Neon y uso de resúmenes en el chat. El opt-in de almacenamiento no equivale a publicar auditorías; no habilitar demo con informes reales identificables ni interpretar roles de demo como permiso de lectura privada. [Seguridad actual](../harness/00_estado_vigente_y_trazabilidad.md).


Este modo permite que un profesor pruebe extracción, revisión, guardado en Neon y dashboard público **sin iniciar sesión en Hugging Face**. No convierte la base de pacientes privada en una base editable por cualquiera. Consulta la [guía completa de Variables y Secrets](hugging-face-variables-y-secrets.md), que cubre también Gemini y las consultas privadas.

## Activación en el único Space de Gradio

| Configuración | Tipo Hugging Face | Valor/propósito |
| --- | --- | --- |
| `ENABLE_ANONYMOUS_DEMO` | Variable | `1` — activa el formulario sin login |
| `DEMO_DATABASE_URL` | **Secret** | conexión a Neon con el rol `health_journey_demo_writer`: EXECUTE sobre la función de demo y, cuando se despliegue migración 005, sobre la función de auditoría Gemini |
| `ENABLE_PUBLIC_DASHBOARD` | Variable | `1` — visualiza exámenes publicados |
| `PUBLIC_DATABASE_URL` | **Secret** | rol `health_journey_public`, SELECT solo sobre vistas públicas |
| `ENABLE_PERSISTENCE` | Variable | Puede permanecer `0`; no es necesario para la demo |
| `DATABASE_URL` | Secret | No se necesita en demo; no proporcionarlo a visitantes |
| `HF_ALLOWED_USERS` | Variable | No se utiliza para guardar demostraciones |

Migración: `db/migrations/004_anonymous_consented_demo.sql`.

## Flujo

1. Abrir la aplicación sin login.
2. Seleccionar un JPG/PDF **previamente anonimizado** (ocultar cédula, nombre, DOB, etc.) y extraer.
3. Revisar unidades, fecha y los valores detectados.
4. Marcar **«Acepto almacenar las mediciones revisadas en Neon»** (desmarcado por defecto).
5. Elegir separadamente **«Publicar las mediciones de este examen en mi dashboard público»** (desmarcado por defecto).
6. Pulsar **«Guardar demostración en Neon (sin login)»**.
7. Ir al **Dashboard público** y pulsar **«Ver progreso público»**. Si no se marcó Publicar, los datos están almacenados en la zona demo pero NO aparecen en la vista.

## Qué se almacena

Solo `anonymous_alias` UUIDv4 generado por sesión, `exam_date` (fecha sin hora), `device_group` sanitizado, fecha de consentimiento y métricas confirmadas y permitidas: código, unidad, segmento, frecuencia y valor. **No se guardan** cédula/ID InBody, nombre, edad, fecha de nacimiento, texto OCR, original_label, nombre/bytes del archivo, hash de origen ni UUID privado del paciente.

Los registros de demostración caducan a los **7 días en la vista**, pero las tablas aún conservan los registros hasta una limpieza administrativa posterior. Se recomienda crear una limpieza periódica de los registros caducados antes de usarlo de forma continua.

Los exámenes publicados son **seudónimos**, no anónimos irreversibles: patrones numéricos, fechas y resultados de composición corporal podrían servir para identificar indirectamente a alguien.

## Aislamiento SQL

- `health_journey_demo_writer` debe recibir únicamente `CONNECT`, `USAGE` y `EXECUTE` sobre `hj_submit_demo_report(uuid,date,text,jsonb,boolean)` y, tras la migración 005, sobre `hj_submit_reviewed_audit(jsonb)`. Sin SELECT/INSERT/UPDATE/DELETE directos en tablas privadas. **Los dos procedimientos tienen contratos distintos:** el demo guarda métricas minimizadas; la auditoría de Gemini conserva información identificable privada y no se publica automáticamente.
- La función `SECURITY DEFINER` tiene `SET search_path = pg_catalog, pg_temp`; `REVOKE EXECUTE FROM PUBLIC` forma parte de la migración. Los objetos se referencian con esquema explícito.
- El validador del lado SQL limita los nombres de las métricas y unidades, rangos, segmentos y frecuencias, máximo 80 filas por examen y un total de 40 envíos cada hora.
- `health_journey_public` recibe SELECT de `hj_demo_public_series`, que muestra solo registros con publicación autorizada **y sin caducar**.
- La opción anónima está **deshabilitada por defecto** si falta el flag o `DEMO_DATABASE_URL`.

**Límite de seguridad importante:** permitir un endpoint de escritura sin autenticación admite potencial abuso y contaminación de datos de demostración. La limitación global ayuda a contenerlo, pero no reemplaza CAPTCHA, firewall, seguimiento operativo ni control de costos. No usar para registros médicos reales de varias personas.

## Pruebas mínimas para el profesor

- Sin consentimiento de almacenamiento, Neon no recibe ningún registro.
- Con almacenamiento marcado y publicación desmarcada, los datos se guardan pero el dashboard público no los muestra.
- Con ambas casillas marcadas, el dashboard muestra fecha sin hora, modelo y mediciones compatibles con un alias UUID aleatorio.
- Un segundo examen guardado en la misma sesión conserva el mismo alias.
- Ningún usuario anónimo puede consultar historiales privados; los botones privados permanecen deshabilitados en modo demo.
- Neon rechaza medidas fuera de la lista permitida y limita el volumen de escritura.
- No hay ID, nombre, edad ni OCR en tablas/vistas de demostración.

**Estado de despliegue:** el CI valida el contrato sintéticamente. Hay que ejecutar la migración, configurar el rol de demo y las dos cadenas de conexión privadas como Secrets, desplegar el commit y comprobar el flujo en el Space. No inferir éxito de ejecución real solo del merge de GitHub.

## Estado de Neon y paso de credenciales

La migración 004 está **aplicada** en `health_journey`. Se verificó que el rol `health_journey_demo_writer` no es superusuario ni puede crear roles; carece de permisos directos de lectura/escritura sobre las tablas privadas y puede ejecutar `hj_submit_demo_report`. La función de auditoría de la migración 005 todavía no está instalada en `main` (comprobado el 1 de noviembre de 2026). La guía distingue estas dos funciones.

El rol `health_journey_demo_writer` **ya tiene LOGIN habilitado** (verificado el 1 de noviembre de 2026). No es necesario volver a habilitarlo ni modificar su contraseña solo para actualizar esta documentación. Confirma que el Secret `DEMO_DATABASE_URL` en Hugging Face use ese rol, base `health_journey` y `sslmode=require`, sin revelar el valor. Para el dashboard configura aparte `PUBLIC_DATABASE_URL` del lector `health_journey_public`.

La casilla de consentimiento **no equivale a autenticación de identidad**: este modo está limitado a pruebas con reportes sintéticos o anonimizados. Los datos que no se aprobaron para publicación no aparecen en el dashboard, pero siguen almacenados temporalmente en las tablas demo.
