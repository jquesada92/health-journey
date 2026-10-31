-- Public analytics release gate for Health Journey.
-- Run as an additive migration, never automatically against live patient data.
-- An examination remains private until its publication has been explicitly authorized.
-- This view exposes monthly COHORT summaries, not de-identified individual records.
-- Suppress all groups smaller than five distinct persons.

ALTER TABLE hj_exams
  ADD COLUMN IF NOT EXISTS public_release_approved_at TIMESTAMPTZ;

CREATE OR REPLACE VIEW hj_public_monthly_summary AS
WITH person_month AS (
    SELECT
        date_trunc('month', e.exam_timestamp)::date AS period_month,
        e.person_uuid,
        CASE
            WHEN e.modelo_inbody ~ '^InBody [0-9]{2,4}$' THEN e.modelo_inbody
            ELSE 'Modelo no especificado'
        END AS device_group,
        m.variable_medida,
        m.unidad_medida,
        CASE WHEN m.segmento IN (
            'left_arm','right_arm','left_leg','right_leg','trunk','whole_body'
        ) THEN m.segmento ELSE NULL END AS segmento,
        m.frecuencia_khz,
        AVG(m.valor_medida) AS personal_monthly_mean
    FROM hj_exams e
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
      )
    GROUP BY 1,2,3,4,5,6,7
)
SELECT
    period_month,
    device_group,
    variable_medida,
    unidad_medida,
    segmento,
    frecuencia_khz,
    COUNT(*)::integer AS participantes,
    ROUND(AVG(personal_monthly_mean), 2) AS valor_promedio
FROM person_month
GROUP BY period_month,device_group,variable_medida,
         unidad_medida,segmento,frecuencia_khz
HAVING COUNT(*) >= 5;

COMMENT ON VIEW hj_public_monthly_summary IS
'Monthly average only from exams with explicit publication consent; minimum 5 persons per group. No identifiers, age, exact dates, or row-level results.';

-- Grant only the public summary read privilege to the existing restricted role
-- where that role exists. Never grant access to private base tables here.
DO $grant$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'health_journey_public') THEN
        CREATE ROLE health_journey_public
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    -- The public role can read ONLY this aggregate view (not the raw tables).
    GRANT CONNECT ON DATABASE health_journey TO health_journey_public;
    GRANT USAGE ON SCHEMA public TO health_journey_public;
    GRANT SELECT ON hj_public_monthly_summary TO health_journey_public;
END
$grant$;

-- A separate, read-only role should be used if public analytics moves
-- to its own service. The current Space backend must never directly expose
-- unrestricted SQL or the private hj_measurements_long view.
