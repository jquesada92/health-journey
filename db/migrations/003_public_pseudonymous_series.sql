-- 003: Publicar series individuales seudonimizadas cuando SU dueño confirme.
-- Aviso: seudonimización NO es anonimización irreversible. El patrón de
-- mediciones y las fechas pueden permitir reidentificación. Nunca publique
-- nombres, cedulas, edad, DOB, archivos, IDs internos, hashes ni texto OCR.
-- Esta migración es aditiva: los exámenes anteriores NO se hacen públicos.

ALTER TABLE hj_persons
    ADD COLUMN IF NOT EXISTS public_alias UUID DEFAULT gen_random_uuid();

UPDATE hj_persons
    SET public_alias = gen_random_uuid()
    WHERE public_alias IS NULL;

ALTER TABLE hj_persons
    ALTER COLUMN public_alias SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_hj_persons_public_alias
    ON hj_persons(public_alias);

CREATE OR REPLACE VIEW hj_public_person_series WITH (security_barrier=true) AS
SELECT
    p.public_alias::text AS anonymous_id,
    e.exam_timestamp::date AS exam_date,
    CASE
      WHEN e.modelo_inbody ~ '^InBody [0-9]{2,4}$'
      THEN e.modelo_inbody
      ELSE 'Modelo no especificado'
    END AS device_group,
    m.variable_medida,
    m.unidad_medida,
    CASE
      WHEN m.segmento IN (
        'left_arm','right_arm','left_leg','right_leg','trunk','whole_body'
      ) THEN m.segmento ELSE NULL
    END AS segmento,
    m.frecuencia_khz,
    m.valor_medida
FROM hj_exams e
JOIN hj_persons p ON p.person_uuid = e.person_uuid
JOIN hj_measurements m ON m.exam_uuid = e.exam_uuid
WHERE e.public_release_approved_at IS NOT NULL
  AND e.exam_timestamp IS NOT NULL
  AND m.confirmation_status = 'confirmed'
  AND m.valor_medida IS NOT NULL
  AND (
    (m.variable_medida = 'weight' AND m.unidad_medida = 'kg')
    OR (m.variable_medida = 'body_fat_mass' AND m.unidad_medida = 'kg')
    OR (m.variable_medida = 'skeletal_muscle_mass' AND m.unidad_medida = 'kg')
    OR (m.variable_medida = 'body_fat_percentage' AND m.unidad_medida = '%')
    OR (m.variable_medida = 'total_body_water' AND m.unidad_medida = 'L')
    OR (m.variable_medida = 'segmental_lean_mass' AND m.unidad_medida = 'kg')
    OR (m.variable_medida = 'segmental_fat_mass' AND m.unidad_medida = 'kg')
    OR (m.variable_medida = 'phase_angle' AND m.unidad_medida = '°')
  );

COMMENT ON VIEW hj_public_person_series IS
'Personal measurement trends for explicitly approved exams, using RANDOM public aliases. Values and dates may reidentify individuals; display no direct PII.';

DO $grant$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'health_journey_public') THEN
        GRANT SELECT ON hj_public_person_series TO health_journey_public;
    END IF;
END
$grant$;
