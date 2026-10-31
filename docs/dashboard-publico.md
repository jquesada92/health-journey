# Dashboard público de estadísticas InBody — privacidad por diseño

Este documento describe el prototipo para visualizar métricas en Hugging Face **sin publicar datos personales, historias individuales o el ID de InBody**.

## Arquitectura obligatoria

Dos instancias independientes del mismo código:

1. **Space privado (ingestión):** autenticación OAuth de Hugging Face, `HF_ALLOWED_USERS`, `DATABASE_URL` con el rol restringido de escritura, `ENABLE_PERSISTENCE=1`, `ENABLE_PUBLIC_DASHBOARD=0`. Aquí se cargan PDF/JPG, revisan OCR, exportan CSV y confirman los exámenes.
2. **Space público (visualización):** `ENABLE_PUBLIC_DASHBOARD=1`, `PUBLIC_DATABASE_URL` como **Secret** con el rol PostgreSQL `health_journey_public`, sin `DATABASE_URL`. Aquí se muestra únicamente el agregado mensual aprobado. El backend rechaza cargas, CSV privados y consultas individuales; la UI deja esas acciones deshabilitadas.

**No convertir el Space de ingesta en público para probar el dashboard.** El upload de Gradio recibe archivos antes de invocar la función Python y, por tanto, no debe exponer un endpoint de subida de informes personales en una instancia pública. Para una separación total de superficies, al desplegar el Space público se recomienda una entrada `public_app.py` mínima que ni siquiera importe los componentes de ingesta (trabajo futuro).

## Anonimización y límites

La vista `hj_public_monthly_summary` se crea mediante `db/migrations/002_public_aggregate_dashboard.sql`.

- Solo incluye exámenes con `public_release_approved_at IS NOT NULL`. **Nada se publica automáticamente**, ni porque se haya guardado correctamente en Neon.
- Solo se publican ocho tipos de variables permitidas: peso, músculo esquelético, grasa kg, grasa %, agua total, masa magra segmental, grasa segmental y ángulo de fase.
- Publica **mes de la evaluación**, no el timestamp exacto; modelo sanitizado, variable, unidad, segmento, frecuencia si corresponde, número de contribuyentes y promedio.
- Cada combinación de mes/modelo/variable/unidad/segmento/frecuencia exige **al menos cinco personas diferentes**. Se promedia primero dentro de cada persona/mes para evitar que alguien con muchas evaluaciones tenga peso desproporcionado.
- **No incluye** nombre, ID del reporte, cédula, UUID, número de archivo, hash de origen, edad, fecha de nacimiento, texto OCR, observación individual o documento.
- La anonimización absoluta no está garantizada; publicar múltiples cohortes en distintos períodos puede producir riesgo de reidentificación o inferencia. Antes de permitir publicaciones reales, completar evaluación de riesgo, consentimiento informado, política de retiro y reducción de información según contexto.
- El historial individual seguirá disponible **solo en el Space privado**; en la vista pública no hay series por paciente.

## Rol público mínimo

En Neon existe el rol `health_journey_public`, creado con `NOLOGIN` para evitar uso accidental hasta configurar una contraseña segura. Se verificaron permisos:
- `SELECT` sobre `hj_public_monthly_summary`: sí.
- `SELECT`/ `INSERT`/ `DELETE` sobre `hj_measurements`: no.
- `SUPERUSER`/ `CREATEROLE`: no.

Antes de conectar el Space público, configura el login y una contraseña única directamente en la consola privada de Neon:

```sql
ALTER ROLE health_journey_public
  WITH LOGIN PASSWORD 'REEMPLAZAR_POR_SECRETO_GENERADO_FUERA_DE_GITHUB';
```

**No publiques esa contraseña ni esta URL en GitHub, mensajes o logs.** Construye un connection string con TLS obligatorio, usando este usuario y la base `health_journey`, y guárdalo como `PUBLIC_DATABASE_URL` (Secret) en el **Space público**, nunca la URL de escritura.

Configura también `ENABLE_PUBLIC_DASHBOARD=1` (Variable). En el Space privado mantenlo en `0`.

## Autorizar publicación

**Pendiente el flujo de consentimiento verificable en la interfaz.** Hasta que exista, no debes ejecutar `UPDATE hj_exams SET public_release_approved_at=...` para exámenes reales por comodidad. Se requiere autorización del titular de cada examen y un procedimiento de revocación y auditoría. El campo SQL es nulo por defecto y la vista pública no tiene datos.

No introducir un botón «publicar todo». El consentimiento es explícito, por examen o por serie de la misma persona, con prueba de autoridad y derecho de revocación.

## Pruebas y despliegue

1. Ejecuta `python -m pytest -q tests/test_public_dashboard.py` y la suite general en un PR.
2. Verifica la migración SQL y permisos con una cuenta administrativa sin exponer credenciales.
3. No active `ENABLE_PUBLIC_DASHBOARD` hasta tener dos entornos separados, roles distintos y consentimiento.
4. Comprueba que el Space público puede consultar la vista, pero no leer `hj_persons` ni `hj_measurements`.
5. Prueba solicitudes manuales a callbacks de carga, exportación o Neon: todas deben bloquearse en modo público.
6. Si la vista responde vacío, mostrar el mensaje correcto: no existen suficientes exámenes publicados para formar cohortes de cinco personas. No presentar resultados ficticios como reales.
