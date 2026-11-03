# Training Hub — FitNotes CSV → Neon

> **Estado al 2026-11-03:** el Captador FitNotes ya existe en `main`, con lectura/validación de CSV de diez columnas, una fila por serie, negativos y decimales, vista previa limitada, `owner_key`, consentimiento de almacenamiento previo al login y escrituras controladas a Neon mediante `training_hub.py` + `migrations/008_fitnotes_training_hub.sql`. El título «propuesta de incorporación» más abajo es HISTÓRICO: no volver a crear una pestaña horizontal ni un checkbox independiente dentro de Training Hub. La ejecución SQL live, la existencia de registros y el E2E del Space no se han comprobado en esta auditoría. Ver [F-08 y AC-V-06](../harness/00_estado_vigente_y_trazabilidad.md).


## Estado (2 noviembre 2026)

Código desarrollado en la rama `feature/training-fitnotes-neon-import-20261102`.
**No fusionado, no desplegado ni probado end-to-end en Hugging Face.**
La migración se probó en una rama temporal de Neon y se aplicó a la rama principal
`health_journey` el 2 de noviembre de 2026, con autorización expresa del usuario.
Se verificó que ambas tablas existen, están vacías y sus permisos privados funcionan. El archivo personal del usuario
no se ha insertado en Neon ni se ha incorporado a GitHub.

## Experiencia de usuario

Se incorpora una pestaña **Training Hub** dentro de `app.py`, sin sustituir
Gradio ni modificar InBody Hub:

1. Iniciar sesión mediante el acceso privado ya configurado (OAuth HF permitido
   o cuenta maestra autenticada).
2. Subir CSV de FitNotes (UTF-8, máximo 10 MiB y 100.000 series).
3. Revisar resumen de días, ejercicios, rango temporal y primeras 60 series.
4. Marcar consentimiento específico **Guardar entrenamiento en Neon**.
5. Opcionalmente confirmar sobrescritura de posiciones de serie previamente
   capturadas cuyos valores han cambiado.
6. Pulsar **Guardar entrenamiento en Neon**. La escritura es transaccional.
7. Consultar las últimas 60 series del usuario autenticado.

La pantalla usa columnas adaptables; en móviles la tabla de 11 columnas
necesita desplazamiento horizontal. No se emplea IA ni se comparte el CSV
con Gemini. No se captura fecha/hora por serie: FitNotes aporta solo fecha.

## Esquema privado

Migración aditiva: `migrations/008_fitnotes_training_hub.sql`.

- `hj_training_imports`: huella SHA-256 del archivo, nombre, propietario,
  fecha y conteo de series nuevas/actualizadas.
- `hj_training_sets`: una fila por serie y posición, fecha, ejercicio,
  categoría, peso/unidad, repeticiones, distancia/unidad, duración en segundos,
  comentarios y referencias a primera/última importación.
- Clave de serie: `owner_key, workout_date, exercise_key, set_number`.
  La posición de serie se cuenta **por ejercicio y fecha, en el orden del CSV**.
  Valores idénticos no son necesariamente duplicados.
- Clave del archivo: `owner_key, source_sha256`; repetir los mismos bytes
  no crea nuevas filas.
- Importaciones acumulativas posteriores: series idénticas se omiten; series
  nuevas se insertan; series cambiadas requieren casilla explícita.
- Las cifras se analizan con `Decimal` y se envían como cadenas a `numeric`
  en PostgreSQL, preservando `8.20`, `0.00` y negativos.
- Duración `H:MM:SS` → segundos, sin adivinar repeticiones o distancias.
- No se crean vistas públicas ni permisos para
  `health_journey_public` o `health_journey_demo_writer`.
- Los datos se consultan exclusivamente con el identificador de propietario
  resuelto en servidor, **nunca uno enviado por el navegador**.

**Límite del algoritmo de deduplicación:** si una aplicación externa
reordena o inserta series en mitad de un mismo ejercicio/día, la identidad
por número de serie puede dejar de corresponder a la misma serie anterior.
La prevalidación avisa cuando los valores difieren; no cambia ni elimina
series existentes sin confirmación. Para conciliación avanzada se requeriría
un identificador persistente de serie desde el origen.

## Migración y despliegue

La migración ya fue aplicada a Neon principal, y se comprobaron los permisos
privados y la ausencia de lecturas públicas. Antes de fusionar o desplegar,
revisar el PR, las pruebas CI y la configuración de autenticación. Activar las
variables privadas ya documentadas de `DATABASE_URL`, `ENABLE_PERSISTENCE`,
`HF_ALLOWED_USERS` o login maestro. Usar URL TLS de rol restringido,
nunca una URL administradora en código. Para un Space público, se recomienda
limitar la visibilidad y habilitar autenticación antes de importar registros.

Pruebas sintéticas:
`python -m pytest -q tests/test_training_hub.py tests/test_training_ui_contract.py`.
No usar el CSV real en fixtures, Git, logs ni documentos.

## Archivo recibido (solo inspección local; no versionado)

El CSV proporcionado en la conversación actual contiene 8.065 series,
507 días y 125 ejercicios distintos, del 2024-09-13 al 2026-11-01.
Incluye tiempos para 9 series y comentarios para 2. Las filas
aparentemente duplicadas pueden corresponder a series diferentes.
