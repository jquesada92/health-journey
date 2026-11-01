-- Canonical long-format read model for InBody Hub.
-- Additive migration: preserves legacy writes, private person UUIDs and existing records.
-- Do not expose this view to the public dashboard database role.
ALTER TABLE public.hj_measurement_catalog
  ADD COLUMN IF NOT EXISTS descripcion_medida text;

INSERT INTO public.hj_measurement_catalog
  (canonical_code, display_label_es, display_label_en, categoria, dimension,
   canonical_unit, comparability_rule, descripcion_medida)
VALUES (
  'phase_angle', 'Ángulo de fase', 'Phase angle', 'bioimpedancia', 'ángulo',
  '°', 'Comparar solo entre mediciones del mismo segmento y frecuencia.',
  'Ángulo derivado de resistencia y reactancia bioeléctricas. Se expresa en grados; no representa un diagnóstico por sí solo.'
)
ON CONFLICT (canonical_code) DO UPDATE SET
  display_label_es = EXCLUDED.display_label_es,
  display_label_en = EXCLUDED.display_label_en,
  canonical_unit = EXCLUDED.canonical_unit,
  descripcion_medida = EXCLUDED.descripcion_medida;

CREATE OR REPLACE VIEW public.hj_measurements_canonical AS
SELECT p.id_persona,
       COALESCE(NULLIF(e.machine_identifier, ''), e.modelo_inbody)::text AS modelo_inbody,
       e.exam_timestamp AS "timestamp",
       (
         regexp_replace(m.variable_medida, '__[0-9]+([.][0-9]+)?khz$', '')
         || CASE WHEN NULLIF(m.segmento, '') IS NOT NULL
              AND regexp_replace(m.variable_medida, '__[0-9]+([.][0-9]+)?khz$', '')
                  NOT LIKE '%__' || m.segmento
              THEN '__' || m.segmento ELSE '' END
         || CASE WHEN m.variable_medida ~ '__[0-9]+([.][0-9]+)?khz$'
              THEN substring(m.variable_medida FROM '(__[0-9]+([.][0-9]+)?khz)$')
              WHEN m.frecuencia_khz IS NOT NULL
              THEN '__' || m.frecuencia_khz::text || 'khz'
              ELSE '' END
       )::text AS variable_medida,
       m.unidad_medida,
       m.valor_medida,
       e.edad
FROM public.hj_measurements AS m
JOIN public.hj_exams AS e ON e.exam_uuid = m.exam_uuid
JOIN public.hj_persons AS p ON p.person_uuid = e.person_uuid;

COMMENT ON VIEW public.hj_measurements_canonical IS
  'Private canonical measurement view: one row per measured value. Do not grant to anonymous/public roles.';

-- Legacy frecuencia_khz columns remain until a separately approved DROP COLUMN
-- migration, after all SQL functions, views and application consumers are updated.
