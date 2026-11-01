-- 005: Consent-only Gemini audit using existing DEMO_DATABASE_URL role.
-- The report ID is private and different separators for the same numeric
-- ID map to a stable random UUID alias. No raw IDs are published.
CREATE TABLE IF NOT EXISTS public.hj_person_aliases (
    normalized_person_id text PRIMARY KEY,
    anonymous_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.hj_extraction_audits
    ADD COLUMN IF NOT EXISTS anonymous_id uuid
    REFERENCES public.hj_person_aliases(anonymous_id);

CREATE OR REPLACE FUNCTION public.hj_submit_reviewed_audit(p_payload jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_id uuid;
    v_anonymous_id uuid;
    v_person_key text;
    v_row jsonb;
    v_items jsonb;
    v_count integer;
    v_index integer := 0;
    v_changed boolean;
    v_marked boolean;
    v_comment text;
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object'
       OR octet_length(p_payload::text) > 2097152 THEN
        RAISE EXCEPTION 'Invalid audit payload';
    END IF;
    IF p_payload->>'source_sha256' !~ '^[0-9a-f]{64}$'
       OR char_length(coalesce(p_payload->>'filename', '')) NOT BETWEEN 1 AND 255
       OR char_length(coalesce(p_payload->>'person_id', '')) NOT BETWEEN 1 AND 128
       OR char_length(coalesce(p_payload->>'model_name', '')) NOT BETWEEN 1 AND 128
       OR jsonb_typeof(p_payload->'raw_response') <> 'object'
       OR jsonb_typeof(p_payload->'measurements') <> 'array' THEN
        RAISE EXCEPTION 'Invalid audit metadata';
    END IF;
    v_items := p_payload->'measurements';
    v_count := jsonb_array_length(v_items);
    IF v_count < 1 OR v_count > 350 THEN
        RAISE EXCEPTION 'Invalid number of measurements';
    END IF;
    IF (p_payload->>'age') IS NOT NULL AND
       (p_payload->>'age')::integer NOT BETWEEN 0 AND 120 THEN
        RAISE EXCEPTION 'Invalid age';
    END IF;

    -- Keep the original label for private audit, normalize only for linkage.
    -- 88571257 and 8-857-1257 must reference the same random alias.
    IF btrim(p_payload->>'person_id') ~ '^[0-9[:space:]-]+$' THEN
        v_person_key := regexp_replace(p_payload->>'person_id', '[^0-9]', '', 'g');
    ELSE
        v_person_key := upper(btrim(p_payload->>'person_id'));
    END IF;
    IF length(v_person_key) NOT BETWEEN 1 AND 128 THEN
        RAISE EXCEPTION 'Invalid normalized person ID';
    END IF;
    INSERT INTO public.hj_person_aliases(normalized_person_id)
    VALUES (v_person_key)
    ON CONFLICT (normalized_person_id)
      DO UPDATE SET normalized_person_id = excluded.normalized_person_id
    RETURNING anonymous_id INTO v_anonymous_id;

    INSERT INTO public.hj_extraction_audits
        (source_sha256, filename, person_id, anonymous_id, exam_datetime, age,
         model_name, raw_response)
    VALUES
        (p_payload->>'source_sha256', p_payload->>'filename',
         p_payload->>'person_id', v_anonymous_id, (p_payload->>'exam_datetime')::timestamp,
         (p_payload->>'age')::integer, p_payload->>'model_name',
         p_payload->'raw_response')
    RETURNING extraction_id INTO v_id;

    FOR v_row IN SELECT value FROM jsonb_array_elements(v_items) AS t(value)
    LOOP
        v_index := v_index + 1;
        IF jsonb_typeof(v_row) <> 'object'
           OR length(trim(coalesce(v_row->>'section', ''))) NOT BETWEEN 1 AND 255
           OR length(trim(coalesce(v_row->>'measurement', ''))) NOT BETWEEN 1 AND 512
           OR length(trim(coalesce(v_row->>'original_section', ''))) NOT BETWEEN 1 AND 255
           OR length(trim(coalesce(v_row->>'original_measurement', ''))) NOT BETWEEN 1 AND 512
           OR length(coalesce(v_row->>'value', '')) NOT BETWEEN 1 AND 64
           OR length(coalesce(v_row->>'original_value', '')) NOT BETWEEN 1 AND 64
           OR (v_row->>'value') !~ '^[+-]?([0-9]+([.,][0-9]+)?|[.,][0-9]+)$'
           OR (v_row->>'original_value') !~ '^[+-]?([0-9]+([.,][0-9]+)?|[.,][0-9]+)$'
           OR length(coalesce(v_row->>'unit', '')) > 32
           OR length(coalesce(v_row->>'original_unit', '')) > 32
           OR length(coalesce(v_row->>'correction_comment', '')) > 2000
           OR jsonb_typeof(v_row->'was_corrected') <> 'boolean' THEN
            RAISE EXCEPTION 'Invalid measurement';
        END IF;
        IF (v_row->>'row_number')::integer <> v_index
           OR v_row->>'filename' IS DISTINCT FROM p_payload->>'filename'
           OR v_row->>'person_id' IS DISTINCT FROM p_payload->>'person_id'
           OR v_row->>'exam_datetime' IS DISTINCT FROM p_payload->>'exam_datetime' THEN
            RAISE EXCEPTION 'Measurement/header mismatch';
        END IF;

        v_changed := (v_row->>'section' IS DISTINCT FROM v_row->>'original_section'
            OR v_row->>'measurement' IS DISTINCT FROM v_row->>'original_measurement'
            OR v_row->>'value' IS DISTINCT FROM v_row->>'original_value'
            OR coalesce(v_row->>'unit', '') IS DISTINCT FROM coalesce(v_row->>'original_unit', ''));
        v_marked := (v_row->>'was_corrected')::boolean;
        v_comment := nullif(trim(v_row->>'correction_comment'), '');
        IF v_marked IS DISTINCT FROM v_changed OR (v_changed AND v_comment IS NULL) THEN
            RAISE EXCEPTION 'Invalid correction audit';
        END IF;

        INSERT INTO public.hj_measurement_audits
            (extraction_id, row_number, section, measurement,
             original_section, original_measurement, original_value,
             original_unit, final_value, final_unit, was_corrected,
             correction_comment, reviewed_at)
        VALUES
            (v_id, v_index, v_row->>'section', v_row->>'measurement',
             v_row->>'original_section', v_row->>'original_measurement',
             v_row->>'original_value', v_row->>'original_unit',
             v_row->>'value', v_row->>'unit', v_changed, v_comment, now());
    END LOOP;
    RETURN v_id;
END
$$;

-- PUBLIC must not be able to invoke the definer function.
REVOKE ALL ON FUNCTION public.hj_submit_reviewed_audit(jsonb) FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO health_journey_demo_writer;
GRANT EXECUTE ON FUNCTION public.hj_submit_reviewed_audit(jsonb)
    TO health_journey_demo_writer;

REVOKE ALL ON public.hj_extraction_audits, public.hj_measurement_audits,
    public.hj_person_aliases FROM health_journey_demo_writer;

-- Private pseudonymous view: never grant to PUBLIC or public dashboard role.
-- Storing an exam does not authorize publishing personal health records.
CREATE OR REPLACE VIEW public.hj_audit_reviewed_private
WITH (security_barrier=true) AS
SELECT e.anonymous_id,
       e.exam_datetime::date AS exam_date,
       m.section, m.measurement, m.final_value AS value,
       m.final_unit AS unit, m.was_corrected
FROM public.hj_extraction_audits e
JOIN public.hj_measurement_audits m USING (extraction_id)
WHERE e.anonymous_id IS NOT NULL;
REVOKE ALL ON public.hj_audit_reviewed_private FROM PUBLIC;
REVOKE ALL ON public.hj_audit_reviewed_private FROM health_journey_demo_writer;

