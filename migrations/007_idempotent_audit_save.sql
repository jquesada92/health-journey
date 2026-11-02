-- 007: Idempotent consent-only audit submission.
-- A repeated upload of the same file is NOT an internal error. Return
-- a safe receipt without granting table SELECT privileges to demo users.
-- Do not silently overwrite previously reviewed rows or raw evidence.
CREATE OR REPLACE FUNCTION public.hj_submit_reviewed_audit_receipt(p_payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_hash text;
    v_existing uuid;
    v_saved uuid;
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'Invalid audit payload';
    END IF;
    v_hash := p_payload->>'source_sha256';
    IF v_hash IS NULL OR v_hash !~ '^[0-9a-f]{64}$'
       OR jsonb_typeof(p_payload->'measurements') <> 'array'
       OR jsonb_array_length(p_payload->'measurements') NOT BETWEEN 1 AND 350 THEN
        RAISE EXCEPTION 'Invalid audit metadata';
    END IF;

    -- The unique SHA-256 key is an exact-document identifier, independent
    -- from filename and human-reviewed corrections. Do not expose metadata.
    SELECT extraction_id INTO v_existing
    FROM public.hj_extraction_audits
    WHERE source_sha256 = v_hash;
    IF v_existing IS NOT NULL THEN
        RETURN jsonb_build_object(
            'status', 'already_saved', 'extraction_id', v_existing
        );
    END IF;

    BEGIN
        v_saved := public.hj_submit_reviewed_audit(p_payload);
    EXCEPTION WHEN unique_violation THEN
        -- Concurrent submissions may have inserted the same document
        -- after the initial check. Only handle conflicts for this hash.
        SELECT extraction_id INTO v_existing
        FROM public.hj_extraction_audits
        WHERE source_sha256 = v_hash;
        IF v_existing IS NULL THEN
            RAISE;
        END IF;
        RETURN jsonb_build_object(
            'status', 'already_saved', 'extraction_id', v_existing
        );
    END;

    RETURN jsonb_build_object('status', 'saved', 'extraction_id', v_saved);
END;
$$;

REVOKE ALL ON FUNCTION public.hj_submit_reviewed_audit_receipt(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.hj_submit_reviewed_audit_receipt(jsonb)
    TO health_journey_demo_writer;
