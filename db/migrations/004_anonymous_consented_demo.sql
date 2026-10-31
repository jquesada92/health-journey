-- 004: An isolated, consent-based anonymous demo writer for classroom QA.
-- Never grant anonymous write privileges to private hj_persons / hj_exams.
-- Run on an authorized branch, with NO personal report content included.
CREATE TABLE IF NOT EXISTS public.hj_demo_exams (
    demo_uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    anonymous_alias uuid NOT NULL,
    exam_date date NOT NULL,
    device_group text NOT NULL,
    storage_consented_at timestamptz NOT NULL DEFAULT now(),
    publish_approved boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '7 days')
);

CREATE TABLE IF NOT EXISTS public.hj_demo_measurements (
    demo_uuid uuid NOT NULL REFERENCES public.hj_demo_exams(demo_uuid) ON DELETE CASCADE,
    row_number integer NOT NULL CHECK (row_number BETWEEN 1 AND 80),
    variable_medida text NOT NULL,
    unidad_medida text NOT NULL,
    segmento text,
    frecuencia_khz numeric(10,3),
    valor_medida numeric(18,6) NOT NULL,
    PRIMARY KEY (demo_uuid, row_number)
);

CREATE INDEX IF NOT EXISTS idx_hj_demo_recent
    ON public.hj_demo_exams(created_at);

CREATE OR REPLACE VIEW public.hj_demo_public_series
WITH (security_barrier = true)
AS
SELECT
    e.anonymous_alias::text AS anonymous_id,
    e.exam_date,
    e.device_group,
    m.variable_medida,
    m.unidad_medida,
    m.segmento,
    m.frecuencia_khz,
    m.valor_medida
FROM public.hj_demo_exams e
JOIN public.hj_demo_measurements m USING (demo_uuid)
WHERE e.publish_approved IS TRUE
  AND e.expires_at > now();

COMMENT ON VIEW public.hj_demo_public_series IS
'Opt-in demo trends only; random alias, date, metric and value. No source IDs, raw OCR or private patient tables. Expires in seven days.';

-- Function is the ONLY grant made to the anonymous demo writer.
-- A fixed trusted search_path and closed EXECUTE privilege prevent escalation.
CREATE OR REPLACE FUNCTION public.hj_submit_demo_report(
    p_alias uuid, p_date date, p_device text, p_measures jsonb,
    p_publish boolean
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    r jsonb;
    report_uuid uuid;
    i integer := 0;
    metric text;
    unit_name text;
    segment text;
    frequency numeric;
    measured numeric;
    model_name text;
BEGIN
    IF p_alias IS NULL OR p_date IS NULL OR p_date < DATE '2010-01-01'
       OR p_date > current_date + 1
       OR p_measures IS NULL OR jsonb_typeof(p_measures) <> 'array'
       OR jsonb_array_length(p_measures) NOT BETWEEN 1 AND 80
       OR p_publish IS NULL THEN
        RAISE EXCEPTION 'Solicitud de demostración inválida';
    END IF;

    -- Bound unattended traffic. Keep records only seven days in public view;
    -- authorized maintenance can purge expired demo rows separately.
    PERFORM pg_advisory_xact_lock(49017031);
    IF (SELECT count(*) FROM public.hj_demo_exams
        WHERE created_at > now() - interval '1 hour') >= 40 THEN
        RAISE EXCEPTION 'Límite temporal de demostración alcanzado';
    END IF;

    model_name := CASE
        WHEN p_device ~ '^InBody [0-9]{2,4}$' THEN p_device
        ELSE 'Modelo no especificado'
    END;

    INSERT INTO public.hj_demo_exams
        (anonymous_alias, exam_date, device_group, publish_approved)
    VALUES (p_alias, p_date, model_name, p_publish)
    RETURNING demo_uuid INTO report_uuid;

    FOR r IN SELECT value FROM jsonb_array_elements(p_measures)
    LOOP
        i := i + 1;
        IF jsonb_typeof(r) <> 'object'
           OR jsonb_typeof(r->'value') <> 'number' THEN
            RAISE EXCEPTION 'Medición inválida';
        END IF;
        metric := r->>'metric';
        unit_name := r->>'unit';
        segment := nullif(r->>'segment', '');
        measured := (r->>'value')::numeric;
        frequency := nullif(r->>'frequency_khz', '')::numeric;

        IF NOT (
            (metric='weight' AND unit_name='kg')
            OR (metric='skeletal_muscle_mass' AND unit_name='kg')
            OR (metric='body_fat_mass' AND unit_name='kg')
            OR (metric='body_fat_percentage' AND unit_name='%')
            OR (metric='total_body_water' AND unit_name='L')
            OR (metric='segmental_lean_mass' AND unit_name='kg')
            OR (metric='segmental_fat_mass' AND unit_name='kg')
            OR (metric='phase_angle' AND unit_name='°')
        ) OR measured NOT BETWEEN -1000 AND 1000
          OR (metric='body_fat_percentage' AND measured NOT BETWEEN 0 AND 100)
          OR (segment IS NOT NULL AND segment NOT IN (
                'left_arm','right_arm','left_leg','right_leg','trunk','whole_body'))
          OR (frequency IS NOT NULL AND frequency NOT BETWEEN 0 AND 1000)
        THEN
            RAISE EXCEPTION 'Medición fuera de las métricas permitidas';
        END IF;
        INSERT INTO public.hj_demo_measurements
            (demo_uuid, row_number, variable_medida, unidad_medida,
             segmento, frecuencia_khz, valor_medida)
        VALUES (report_uuid, i, metric, unit_name, segment, frequency, measured);
    END LOOP;
    RETURN report_uuid;
END
$function$;

-- Execute grant must not default to all users.
REVOKE ALL ON FUNCTION public.hj_submit_demo_report(
    uuid, date, text, jsonb, boolean
) FROM PUBLIC;

DO $role$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'health_journey_demo_writer'
    ) THEN
        CREATE ROLE health_journey_demo_writer
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    GRANT CONNECT ON DATABASE health_journey TO health_journey_demo_writer;
    GRANT USAGE ON SCHEMA public TO health_journey_demo_writer;
    GRANT EXECUTE ON FUNCTION public.hj_submit_demo_report(
        uuid, date, text, jsonb, boolean
    ) TO health_journey_demo_writer;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'health_journey_public'
    ) THEN
        GRANT SELECT ON public.hj_demo_public_series
            TO health_journey_public;
    END IF;
END
$role$;

-- No DELETE on real tables. Authorized maintenance can periodically run:
-- DELETE FROM public.hj_demo_exams WHERE expires_at < now();
