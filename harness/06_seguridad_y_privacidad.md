# 06 — Seguridad, privacidad y control de acceso

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
