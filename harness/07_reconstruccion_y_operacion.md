# 07 — Manual de reconstrucción desde cero y operación


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
`AUDIT_DATABASE_URL` (Secret HF), usuario exacto
`health_journey_audit_submit`, SSL y
`ENABLE_ANONYMOUS_AUDIT=1` (Variable HF). El nuevo rol se crea en
`migrations/005_consent_only_audit_writer.sql` como `NOLOGIN`
para que un administrador establezca su contraseña por canal seguro
y habilite el login **después** de aplicar la migración. No usar
la creación automática de roles Neon: puede heredar
`neon_superuser`.

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


## Infraestructura actual: Gemini Flash sobre Space ZeroGPU existente (2026-11-01)

El PR #38 ya fue fusionado en `main`. La extracción utiliza Gemini Flash
por API y **no necesita GPU** para procesar los InBody. Sin embargo, el Space
`jaqo/health-journey` sigue asignado a hardware **ZeroGPU** y el usuario
no dispone de CPU Basic en sus opciones de hardware. ZeroGPU exige una
función `@spaces.GPU` conectada a un evento de Gradio para superar el
control de arranque. La solución de compatibilidad es un **diagnóstico CUDA
opcional** asociado a un botón en un acordeón cerrado; no se usa en
`extract_gemini` ni en `save_audit`. Solo al pulsar el diagnóstico se
solicita GPU y se consume la cuota correspondiente.

`app.py` importa `spaces` y registra la función decorada antes de
construir la interfaz. `requirements.txt` mantiene `gradio[oauth]` y
`spaces`. No reinstalar EasyOCR/PaddleOCR para este workaround ni eliminar
el soporte ZeroGPU de la infraestructura hasta que haya otro hardware
disponible. Tras fusionar este PR, verificar el nuevo build del Space y
los flujos de extracción, revisión y consentimiento. Esta compatibilidad
no constituye una validación end-to-end.


## Estado vigente — 1 de noviembre de 2026 (PR #38, pendiente de validación E2E)

La interfaz activa de **InBody Hub** es Gradio y usa **Gemini Flash** mediante
`inbody_mvp/gemini_review.py` para extraer el examen actual de PDF/JPG/PNG.
El envío a Google exige consentimiento separado por documento. No se capturan
gráficos de historial. El encabezado (fecha/hora, archivo, ID y edad) se repite
en cada fila; `section`, `measurement`, `value`, `unit` forman el contrato
de mediciones. El nombre de la medición incluye el segmento corporal cuando
corresponde. Frecuencia es una medición por fila, y Puntaje InBody también.

La tabla permite revisar cada fila y corregir sección, nombre, valor y unidad.
Se conservan el valor original de Gemini, indicador calculado de corrección,
comentario obligatorio al corregir y estado revisado. Los decimales se
preservan como texto (ej. `8.20`). El guardado en Neon es una **auditoría privada**
separada de las tablas de historial y requiere OAuth, consentimiento y
`migrations/004_gemini_measurement_audit.sql`. No está comprobado el
despliegue E2E ni ejecutada esa migración.

**Componentes retirados del runtime/despliegue:** visor y editor de secciones,
EasyOCR y PaddleOCR. Los módulos y pruebas de OCR heredados permanecen
en el repositorio como material legacy; no se distribuyen en el Space. La
demostración anónima y el CSV antiguo no son parte del flujo activo de carga,
aunque subsisten módulos de compatibilidad y el dashboard público/historial.
No confundir documentación histórica del MVP con su estado operativo actual.


## 0. Prerrequisitos

- Permiso de acceso al repositorio `jquesada92/health-journey` y su historial de ramas.
- Python 3.12, `git` y acceso a terminal. RAM/CPU suficiente para EasyOCR local.
- Acceso legítimo a Neon, GitHub Actions y Hugging Face Spaces.
- Datos **sintéticos** para pruebas de reconstrucción. Nunca copiar registros de producción a un entorno público.
- Confirmar la revisión de seguridad del despliegue antes de usar datos sensibles.

## 1. Recuperar fuente y documentos

```bash
git clone https://github.com/jquesada92/health-journey.git
cd health-journey
git fetch --all --prune
git status
```

Abrir `harness/README.md`, leer los documentos 01–09 y `PROMPT_AGENTE.md`. Verificar los PR relevantes antes de decidir qué rama usar; el código del repositorio es la verdad sobre lo implementado, el harness es la verdad sobre lo requerido.

Crear una rama nueva para reconstruir; nunca sobrescribir `main` o borrar recursos remotos en la primera prueba.

## 2. Entorno Python local

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
python -m compileall -q app.py inbody_mvp
python -m pytest -q tests
```

En Windows, usar el activador correspondiente de `.venv`. El OCR local puede descargar pesos iniciales de EasyOCR; validar permisos y fuentes, y documentar compatibilidad de CPU/GPU. No prometer ZeroGPU en desarrollo local.

Copiar `.env.example` a `.env` **localmente**, introducir únicamente valores autorizados y verificar que `.env` esté en `.gitignore`.

## 3. Levantar aplicación sin Neon

```bash
# .env: ENABLE_PERSISTENCE=0
python app.py
```

Abrir `http://127.0.0.1:7860`. Probar con reporte sintético:
- archivo válido e inválido;
- candidatos, advertencias y tabla editable;
- exportación CSV sin `DATABASE_URL`;
- contrato de siete columnas;
- hash + timestamp exportación en nombre (función objetivo; implementar si todavía falta);
- carga de múltiples CSV para visualizar (función objetivo; implementar si todavía falta).

## 4. Recrear Neon (si el proyecto original ya no está disponible)

**No crear otro proyecto si el existente sigue operativo.** Neon actual verificado:
- Proyecto: `health-journey`.
- ID: `autumn-pond-85488960` (identificador de recurso, no contraseña).
- Base: `health_journey`.
- Región: `aws-us-east-1`.
- PostgreSQL: 17.
- Rama inicial: `main`.

Secuencia para una reconstrucción nueva:
1. Crear un proyecto Neon con nombre coherente y una base `health_journey` (región/versión compatibles).
2. Crear tablas y vista mediante **migraciones**. El esquema inicial reproducible está en `db/schema.sql`; aplicarlo a una BD **vacía**, sin tablas previas o datos que puedan ser sobreescritos.
3. Verificar índices, restricciones de unicidad, foreign keys, unidades, vistas y tipo de timestamp.
4. Crear un rol **no administrativo** de aplicación y conceder solo `CONNECT`, `USAGE`, `SELECT`/`INSERT`/`UPDATE` sobre objetos requeridos; catálogo y vista de consulta solo lectura.
5. Verificar roles heredados: un rol sin `SUPERUSER` puede seguir teniendo permisos amplios. No usar credenciales del propietario ni el rol inicial `health_journey_app`.
6. Generar credenciales con longitud/entropía adecuadas, configurar TLS obligatorio, rotación y recuperación segura. No imprimir la URL.
7. Ejecutar inserción sintética transaccional, consulta y prueba de duplicado; después eliminar el fixture solo en una BD de pruebas controlada, con aprobación y sin mezclar datos reales.

**Si ya existen datos:** restaurar desde backup probado o migrar de forma controlada; el DDL inicial no reemplaza copias de seguridad ni migraciones futuras.

## 5. Integrar Neon local

Ejemplo de `.env` (NO subir archivo real):

```dotenv
DATABASE_URL=postgresql://USUARIO_RESTRINGIDO:CONTRASENA_URL_ENCODED@HOST/health_journey?sslmode=require
ENABLE_PERSISTENCE=1
```

Reiniciar `python app.py` y ejecutar flujo de revisión + guardado **en localhost y con datos sintéticos**. Confirmar que una nueva fila aparece en `hj_exams` y sus medidas en `hj_measurements` y `hj_measurements_long`. Repetir el mismo archivo y comprobar respuesta de duplicado. No se debe guardar nada antes de pulsar «Confirmar».

## 6. Desplegar en Hugging Face Spaces

Configuración prevista del `README.md` de la aplicación:

```yaml
sdk: gradio
app_file: app.py
hf_oauth: true
```

Space previsto: `jaqo/health-journey`. Mantener Gradio y ZeroGPU cuando la compatibilidad esté verificada. **Para datos reales, configurar el Space como privado** y seguir el documento 06.

### Secretos y variables del Space

| Tipo | Nombre | Valor |
| --- | --- | --- |
| Secret | `DATABASE_URL` | URL PostgreSQL TLS del rol restringido |
| Variable | `ENABLE_PERSISTENCE` | `0` para pruebas públicas; `1` solo tras validación de seguridad |
| Variable | `HF_ALLOWED_USERS` | Usuario(s) HF permitidos, separados por coma |

No introducir secretos en el repositorio. Activar OAuth y validar el perfil en **cada** callback SQL. Reiniciar el Space tras cambiar variables y verificar logs sin datos personales.

### Sincronización desde GitHub

Workflow: `.github/workflows/deploy-huggingface.yml`. Requiere:
- Secret GitHub `HF_TOKEN` (token de escritura sobre el Space).
- Variable GitHub `HF_SPACE_ID` con `jaqo/health-journey`.
- En el staging de la acción: `app.py`, `README.md`, `requirements.txt` y **todos los módulos Python importados** en `inbody_mvp/`. Si se añade `dashboard.py` o `exports.py`, ampliar la lista de archivos del workflow; de lo contrario el Space fallará por `ModuleNotFoundError`.

El workflow se ejecuta al cambiar rutas relevantes en `main` o manualmente con `workflow_dispatch`. La mera publicación en GitHub **no certifica** que el Space haya iniciado ni que la BD responda. Revisar logs de GitHub y de Hugging Face.

## 7. Comprobación de extremo a extremo

Con datos sintéticos y un usuario autorizado:
1. Abrir Space privado → autenticar.
2. Cargar documento de prueba → extraer → revisar y corregir.
3. Exportar CSV → comprobar nombre y siete columnas.
4. Guardar en Neon → obtener confirmación después de transacción.
5. Consultar historial desde la pestaña Dashboard/Neon → validar coincidencia.
6. Cargar ese CSV junto con otro CSV distinto → mostrar histórico sin escritura SQL.
7. Cambiar modelo/segmento/frecuencia → comprobar que Plotly no une mediciones incompatibles.
8. Probar usuario distinto → bloqueo de lectura/escritura.
9. Consultar recuento de registros antes/después de la importación CSV: no debe cambiar.

## 8. Recuperación, fallos y rollback

| Incidente | Actuación |
| --- | --- |
| Space sin botón de guardado | Revisar despliegue y variables; el botón debe mostrar estado y no saltarse autorización |
| Error de autenticación | Revisar configuración OAuth y username exacto sin imprimir token |
| `ModuleNotFoundError` | Confirmar nuevos módulos en workflow de sincronización |
| SQL de «permiso denegado» | Revisar privilegios efectivos de rol restringido; no usar rol admin como solución rápida |
| CSV incompatible | Mostrar diferencias de encabezado y contrato; no aceptar datos silenciosamente |
| OCR erróneo en otra plantilla | Revertir parser afectado, conservar OCR bruto en memoria y añadir fixture sintético |
| Datos erróneos guardados | Marcar para revisión y diseñar corrección auditada; no ejecutar `DELETE` masivo |
| BD inaccesible | Mantener exportación y dashboard CSV funcionales; deshabilitar temporalmente Neon |
| Despliegue defectuoso | Revertir al commit probado; restaurar `README` y workflow compatibles; no borrar base |

Documentar RTO/RPO y retención de backups antes de producción; no asumir garantías de un plan específico de Neon o Hugging Face.

## 9. Integridad y limpieza

- Ejecutar CI en cada PR.
- Revisar reporte de cambios de esquema antes de migrar.
- No reusar credenciales de producción en QA.
- Mantener backups externos verificados de DB y CSV confirmados según la política privada.
- Nunca prometer reconstrucción completa de los reportes originales si no se conservaron sus bytes o una copia segura fuera de Neon.
