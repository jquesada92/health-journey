-- 007: Safe repeat-upload detection and explicitly confirmed logical overwrite.
-- Same filename (case-insensitive), or same binary SHA256: already processed.
-- Conflicting (normalized person ID, exam timestamp, measurement): confirm.
-- Old audits stay immutable; private dashboard selects the latest version.
-- All write checks run inside a single database transaction with locks.

CREATE OR REPLACE FUNCTION public.hj_audit_filename_processed(p_filename text)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF length(btrim(coalesce(p_filename, ''))) NOT BETWEEN 1 AND 255 THEN
        RETURN false;
    END IF;
    RETURN EXISTS (
        SELECT 1 FROM public.hj_extraction_audits e
        WHERE lower(btrim(e.filename)) = lower(btrim(p_filename))
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.hj_submit_reviewed_audit_receipt(
    p_payload jsonb,
    p_confirm_overwrite boolean DEFAULT false,
    p_preflight boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_hash text;
    v_filename text;
    v_person_key text;
    v_exam timestamp;
    v_measurements jsonb;
    v_conflicts integer;
    v_id uuid;
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'Invalid audit payload';
    END IF;
    v_hash := p_payload->>'source_sha256';
    v_filename := btrim(p_payload->>'filename');
    v_measurements := p_payload->'measurements';
    IF v_hash IS NULL OR v_hash !~ '^[0-9a-f]{64}$'
       OR length(v_filename) NOT BETWEEN 1 AND 255
       OR jsonb_typeof(v_measurements) <> 'array'
       OR jsonb_array_length(v_measurements) NOT BETWEEN 1 AND 350
       OR length(btrim(coalesce(p_payload->>'person_id', ''))) NOT BETWEEN 1 AND 128
       OR length(btrim(coalesce(p_payload->>'exam_datetime', ''))) NOT BETWEEN 10 AND 32 THEN
        RAISE EXCEPTION 'Invalid audit metadata';
    END IF;
    v_exam := (p_payload->>'exam_datetime')::timestamp;

    IF btrim(p_payload->>'person_id') ~ '^[0-9[:space:]-]+$' THEN
        v_person_key := regexp_replace(p_payload->>'person_id', '[^0-9]', '', 'g');
    ELSE
        v_person_key := upper(btrim(p_payload->>'person_id'));
    END IF;
    IF length(v_person_key) NOT BETWEEN 1 AND 128 THEN
        RAISE EXCEPTION 'Invalid normalized person ID';
    END IF;

    -- Order is stable across callers: filename lock, followed by exam lock.
    -- A separate hash is also checked to block renamed copies.
    PERFORM pg_advisory_xact_lock(hashtextextended('audit-file:' || lower(v_filename), 0));
    PERFORM pg_advisory_xact_lock(
        hashtextextended('audit-exam:' || v_person_key || ':' || v_exam::text, 0)
    );

    IF EXISTS (
        SELECT 1 FROM public.hj_extraction_audits e
        WHERE lower(btrim(e.filename)) = lower(v_filename)
           OR e.source_sha256 = v_hash
    ) THEN
        RETURN jsonb_build_object('status', 'filename_processed');
    END IF;

    SELECT count(*) INTO v_conflicts
    FROM jsonb_array_elements(v_measurements) AS incoming(row_value)
    WHERE EXISTS (
        SELECT 1
        FROM public.hj_extraction_audits e
        JOIN public.hj_person_aliases p ON p.anonymous_id = e.anonymous_id
        JOIN public.hj_measurement_audits m ON m.extraction_id = e.extraction_id
        WHERE p.normalized_person_id = v_person_key
          AND e.exam_datetime = v_exam
          AND lower(btrim(m.measurement)) =
              lower(btrim(incoming.row_value->>'measurement'))
    );

    IF v_conflicts > 0 AND p_confirm_overwrite IS NOT TRUE THEN
        RETURN jsonb_build_object(
            'status', 'overwrite_required', 'conflicts', v_conflicts
        );
    END IF;
    IF p_preflight IS TRUE THEN
        RETURN jsonb_build_object('status', 'ready', 'conflicts', v_conflicts);
    END IF;

    -- Re-use the tested, write-validated procedure. A new version is
    -- appended for provenance; the view below exposes ONLY the latest
    -- record per person + exact timestamp + measurement.
    v_id := public.hj_submit_reviewed_audit(p_payload);
    RETURN jsonb_build_object(
        'status', CASE WHEN v_conflicts > 0 THEN 'overwritten' ELSE 'saved' END,
        'conflicts', v_conflicts
    );
END;
$$;

-- Source audits are append-only. Show the most recent extraction's
-- measurements for any identical (person, exam datetime, measurement).
-- Dense rank deliberately retains repeated values of the same measurement
-- *within* a single extraction (such as impedance frequencies).
CREATE OR REPLACE VIEW public.hj_audit_reviewed_private
WITH (security_barrier=true) AS
WITH revisions AS (
    SELECT e.anonymous_id, e.exam_datetime,
           m.section, m.measurement,
           m.final_value AS value, m.final_unit AS unit,
           m.was_corrected,
           dense_rank() OVER (
               PARTITION BY e.anonymous_id, e.exam_datetime,
                            lower(btrim(m.measurement))
               ORDER BY e.created_at DESC, e.extraction_id DESC
           ) AS version_rank
    FROM public.hj_extraction_audits e
    JOIN public.hj_measurement_audits m USING (extraction_id)
    WHERE e.anonymous_id IS NOT NULL
)
SELECT anonymous_id, exam_datetime::date AS exam_date,
       section, measurement, value, unit, was_corrected
FROM revisions
WHERE version_rank = 1;

REVOKE ALL ON FUNCTION public.hj_audit_filename_processed(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.hj_submit_reviewed_audit_receipt(jsonb,boolean,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.hj_audit_filename_processed(text)
    TO health_journey_demo_writer;
GRANT EXECUTE ON FUNCTION public.hj_submit_reviewed_audit_receipt(jsonb,boolean,boolean)
    TO health_journey_demo_writer;
REVOKE ALL ON public.hj_audit_reviewed_private FROM PUBLIC;
REVOKE ALL ON public.hj_audit_reviewed_private FROM health_journey_demo_writer;
GRANT SELECT ON public.hj_audit_reviewed_private
    TO health_journey_app, health_journey_runtime;
