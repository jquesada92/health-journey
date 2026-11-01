# 06 — Seguridad, privacidad y control de acceso


## Identidad InBody: vinculación privada y seudónimo en consultas

Un ID numérico con separadores, por ejemplo `88571257` y
`8-857-1257`, se normaliza a la misma clave interna `88571257`
(sin espacios ni guiones; **sin quitar ceros iniciales**).
Para IDs alfanuméricos se conservan los separadores y se estandariza
el uso de mayúsculas. Nunca se utiliza el número del reporte, ni su
hash determinístico, como alias visible.

La migración 005 crea `hj_person_aliases`: clave canónica **privada**
y un UUID aleatorio persistente `anonymous_id`. Al insertar cada
auditoría, la función asigna el UUID de la persona; dos informes con
el mismo ID normalizado comparten alias. El ID tal como aparece en
el PDF sigue conservado solo en `hj_extraction_audits.person_id`
y en el JSON original de auditoría, sin acceso público.

La vista `hj_audit_reviewed_private` devuelve solamente UUID,
**fecha sin hora**, sección, medición, valor, unidad y estado de
corrección. Excluye `person_id`, `filename`, edad, hora exacta y
`raw_response`. Su acceso se limita a roles privados; en Gradio,
`load_reviewed_audit_history` exige OAuth antes de consultar.
El formulario recibe el ID real en un campo visualmente oculto
y muestra únicamente `Persona <alias>` en tabla/gráfica.

El rol `health_journey_demo_writer` conserva permiso de **ejecución
de la función de inserción**, pero ninguno de lectura de alias,
mapa de IDs o auditorías. El dashboard público **no** consulta
auditorías privadas automáticamente: consentir almacenamiento en
Neon no constituye consentimiento de publicación. Exponer
tendencias individuales requeriría un consentimiento separado
y una revisión del riesgo de reidentificación. Un UUID es
*seudonimización*, no garantía de anonimato absoluto.

El esquema se probó en rama temporal de Neon con **IDs sintéticos**
equivalentes: dos exámenes → un mismo UUID; sin acceso SELECT para
roles públicos o de demostración. La migración 005 de `main` de
Neon permanece pendiente de aprobación, así que el guardado y la
consulta de esta vista no están activos aún en producción.



## Flujo actual: extracción inglés + PDF y consentimiento (noviembre 2026)

**UI:** InBody Upload coloca, antes del archivo, dos consentimientos
independientes (Gemini y Neon, ambos apagados). El PDF se renderiza
localmente en una galería Gradio 6 junto a la tabla editable; se
pueden inspeccionar páginas en pantalla completa. El visor no envía
el documento a Gemini. Al cargar otro archivo se revocan ambos
consentimientos y se limpian resultados anteriores.

**Extracción:** Gemini traduce los nombres al inglés, incluso si el
documento está en español: `Body Composition Analysis`,
`Segmental Lean Analysis`, `Right Arm - Lean Mass`,
`Right Arm - Frequency`, `InBody Score`. El número sigue como
texto exacto (ej. `8.20`) y cada frecuencia ocupa su propia fila.
No se extraen valores del historial. Se conserva la respuesta
original, la corrección y su comentario.

**Escritura sin OAuth:** la auditoría solo se guarda tras revisión
y consentimiento Neon. Se ejecuta `hj_submit_reviewed_audit(jsonb)`
usando una conexión **distinta** de `DATABASE_URL`:
`DEMO_DATABASE_URL` (Secret HF), usuario exacto
`health_journey_demo_writer`, SSL y
`ENABLE_ANONYMOUS_DEMO=1` (Variable HF). La migración
`migrations/005_consent_only_audit_writer.sql` **reutiliza** el rol
`health_journey_demo_writer` y no crea usuarios ni modifica contraseñas.
Solo concede permiso EXECUTE sobre la función de auditoría; el rol sigue
sin acceso directo de lectura o escritura sobre tablas privadas.

El rol solo puede ejecutar la función de inserción y no posee
permisos SELECT/INSERT/UPDATE/DELETE directos sobre las tablas.
La función valida límites de tamaño, metadatos, valores,
correcciones y registra todas las filas en una sola transacción.
El historial privado sigue requiriendo OAuth y no se expone al
público. Esto no constituye autenticación del remitente: se
necesitan protección antiabuso y hosting privado para datos
identificables. El dashboard público continúa independiente.

El cambio está preparado en rama y probado en una rama temporal
de Neon con datos sintéticos; **no desplegado en Neon main**.
No se modificaron tablas históricas ni usuarios existentes.



## Envío a Gemini y auditoría (actualizado)

La carga a Google Gemini requiere consentimiento **por documento**, separado
del consentimiento de guardar en Neon. El Space público solo puede usarse con
documentos sintéticos o anonimizados. Nunca registrar imágenes, IDs,
JSON bruto, textos extraídos ni credenciales en logs de CI. Verificar la
política de retención y uso de datos del nivel de API elegido.

Las nuevas tablas de auditoría contienen información identificable
(`person_id`, `filename`, `raw_response`) y deben permanecer privadas.
El método de guardado valida OAuth + `HF_ALLOWED_USERS`, pero también es
necesario restringir en PostgreSQL los permisos efectivos del rol de aplicación;
no conceder acceso al rol público ni al rol de demostración. El proyecto
actual no tiene la opción HIPAA activada: no asumir certificación clínica.


> **Categoría de información:** los exámenes de composición corporal y sus identificadores son datos personales de salud/bienestar potencialmente sensibles. El prototipo no debe interpretarse como una plataforma clínica aprobada.

## 1. Amenazas principales

| Riesgo | Mitigación mínima |
| --- | --- |
| Consulta de resultados de otra persona | Autenticación, autorización del servidor y aislamiento por propietario |
| Una clave de base filtrada en GitHub/Space | Secrets, rotación, nunca imprimir connection strings; no usar propietario/admin |
| Un Space público procesa un reporte identificable | Space privado + autenticación + consentimiento; pruebas públicas exclusivamente sintéticas/anonimizadas |
| CSV malicioso o gigante | Validar tamaño/filas/headers/UTF-8; no ejecutar fórmulas ni código; limitar sesiones |
| OCR confunde un número de referencia con medición | Revisión humana obligatoria, procedencia y regresiones por plantilla |
| Múltiples usuarios comparten cachés o temporales | Datos por sesión; borrado/retención definida; rutas no adivinables |
| SQL injection | Consultas parametrizadas mediante SQLAlchemy; no interpolar filtros de UI en SQL |
| Corrupción por duplicados/reintentos | Hash de documento y transacción indivisible |
| Acceso con privilegios elevados | Rol dedicado, `CONNECT/USAGE/SELECT/INSERT/UPDATE` donde corresponda, **sin DELETE, CREATE, CREATEROLE ni membresía administrativa** |
| Exposición en logs/CI/observabilidad | Redactar datos, no adjuntar archivos personales, métricas agregadas sin PII |

## 2. Política de identidad

En `app.py` se presenta `gr.LoginButton` cuando procede. **La sesión OAuth debe validarse del lado servidor para cada función que consulta o modifica Neon**. El env `HF_ALLOWED_USERS` actúa como allowlist inicial para un solo propietario o equipo pequeño, no como sistema multiinquilino.

**Importante:** una lista de usuarios autorizados sin control por propietario de cada fila permite que todos los miembros de esa lista consulten todos los registros accesibles mediante el mismo rol de BD. Antes de permitir multiusuario real, implementar identidad verificada, ownership de persona/examen, controles por fila o RLS, pruebas de acceso cruzado y auditoría. El `id_persona` del documento **no** constituye autenticación.

Si el Space se mantiene público para QA, usar solo ejemplos ficticios o realmente anonimizados, sin importar si existe una allowlist para guardar.

## 3. Secretos y variables

| Lugar | Clave | Naturaleza |
| --- | --- | --- |
| Hugging Face Space → Secrets | `DATABASE_URL` | **Secreto**: conexión PostgreSQL con `sslmode=require` y rol restringido |
| Hugging Face Space → Variables | `ENABLE_PERSISTENCE` | Interruptor: `1` solo cuando la seguridad y la conexión estén verificadas |
| Hugging Face Space → Variables | `HF_ALLOWED_USERS` | Usernames HF permitidos, separados por comas; no son contraseñas |
| GitHub Actions → Secrets | `HF_TOKEN` | Token HF con permisos mínimos para desplegar |
| GitHub Actions → Variables | `HF_SPACE_ID` | Nombre del Space, p. ej. `jaqo/health-journey` |
| Desarrollo local → `.env` | `DATABASE_URL` y `ENABLE_PERSISTENCE` | Solo local; ignorado por Git |
| Entorno aplicación | `SPACE_ID` | Identificador proporcionado en Spaces; no inventar manualmente para «saltarse» validaciones |

Nunca copiar valores privados a `README`, issues, PR, capturas de pantalla, logs, informes de pruebas o archivos comprimidos del harness. `.env.example` contiene **solo placeholders**.

## 4. Neon: mínimo privilegio efectivo

El proyecto Neon se llama `health-journey` y la base `health_journey`. El rol de aplicación previsto es `health_journey_runtime`, no el propietario. Verificar **privilegios efectivos y membresías**, no solo `rolsuper=false`: un rol puede heredar permisos administrativos por membresía.

Consulta de comprobación sin imprimir secretos:

```sql
SELECT
  r.rolname,
  r.rolcanlogin,
  r.rolcreaterole,
  has_table_privilege(r.rolname, 'hj_measurements', 'SELECT') AS puede_leer,
  has_table_privilege(r.rolname, 'hj_measurements', 'INSERT') AS puede_insertar,
  has_table_privilege(r.rolname, 'hj_measurements', 'DELETE') AS puede_borrar
FROM pg_roles r
WHERE r.rolname = 'health_journey_runtime';
```

**Criterio de seguridad:** `puede_borrar = false` y `rolcreaterole = false`; comprobar también que no hereda `neon_superuser`. El rol `health_journey_app` creado en una iteración inicial adquirió privilegios amplios por membresía; **no utilizarlo como credential de Hugging Face**.

No introducir cambios destructivos de roles/permisos sin revisión y procedimiento de recuperación.

## 5. Política de archivos

- No subir PDF/JPG/PNG de personas reales a GitHub o fixtures.
- En el MVP Neon almacena el hash del archivo fuente, los metadatos y medidas confirmadas; **no** el documento original. Si se implementa almacenamiento de originales, definir cifrado, roles, consentimiento, URL de acceso temporal, retención y eliminación.
- Exportaciones CSV también contienen información sensible; ofrecer descarga directa bajo sesión y borrado de temporales por política, sin logs del contenido.
- Deshabilitar endpoints de depuración, stacktraces y trazas OCR que incluyan identificadores.
- Evitar nombres de archivos con identificación personal; aplicar SHA-256+timestamp UTC.
- No compartir un archivo CSV subido por un usuario con otro usuario/sesión.

## 6. Criterios de privacidad para lanzamiento

1. Entorno privado y cuentas autorizadas.
2. Role PostgreSQL mínimo, comprobado.
3. Autorización real de cada lectura y escritura; sesión OAuth auténtica.
4. Pruebas de usuario no autenticado, usuario distinto y bypass de la interfaz/API.
5. Políticas de retención de ficheros temporales, logs y respaldos.
6. Backups/restore probados y plan de eliminación a petición.
7. Evaluación legal y de cumplimiento aplicable antes de tratar datos clínicos o permitir multiusuario.
8. No considerar una configuración de Space privado como sustituto automático de los controles anteriores.

## 7. Pruebas críticas

- Sin `DATABASE_URL` o con `ENABLE_PERSISTENCE=0`: no conectar ni guardar.
- En Space con `HF_ALLOWED_USERS` configurado, el usuario no autenticado o no autorizado no puede consultar ni guardar.
- Un usuario no puede cambiar el ID en una petición para leer datos ajenos cuando se introduzca soporte multiusuario.
- La ruta «cargar CSV» no ejecuta SQL de escritura.
- Un CSV con fórmula, número no finito, encabezado inesperado o tamaño excesivo no causa ejecución ni acceso indebido.
- Secretos nunca aparecen en el HTML, excepciones visibles o logs de CI.

**Un resultado correcto en tests sintéticos no certifica por sí solo un despliegue seguro sobre datos reales.**
