# Gemini Flash: revisión y auditoría por medición

La pestaña InBody Upload sustituye el visor de secciones por extracción Gemini y tabla editable; se preservan los dashboards.

## Configuración
- Instalar requirements.txt.
- GEMINI_API_KEY como secreto; GEMINI_MODEL opcional (gemini-2.5-flash por defecto).
- En Neon privado aplicar migrations/004_gemini_measurement_audit.sql.
- Configurar DATABASE_URL con SSL, ENABLE_PERSISTENCE=1 y HF_ALLOWED_USERS para Spaces.
- Evitar cargar documentos identificables en Spaces públicos: Google recibe la imagen.

## Procedimiento
1. Cargar PDF/JPG/PNG y extraer con Gemini Flash.
2. Revisar cada fila, incluso si no necesita corrección.
3. Corregir value, unit, section o measurement; original_value permanece inmutable.
4. Completar correction_comment si hubo modificación y marcar reviewed en cada fila.
5. Validar revisión, aceptar el guardado privado y guardar.

was_corrected se calcula comparando contra la respuesta original; la columna mostrada no se toma como autoridad. El valor decimal permanece como texto, con validación Decimal, para conservar 8.20.

## Auditoría Neon
- hj_extraction_audits conserva archivo, encabezado, modelo y respuesta original completa de Gemini.
- hj_measurement_audits conserva la medición original y final, bandera de corrección, comentario y fecha de revisión.
- La operación es atómica y rechaza el mismo archivo dos veces.
- No se inserta en las tablas existentes hj_exams/hj_measurements: esta etapa de auditoría está separada del historial y dashboards.

## Pruebas
pytest tests/test_gemini_measurement_audit.py

Sin API key de Gemini y base Neon no se validan llamadas reales ni persistencia; estas pruebas verifican la lógica local de revisión.
