-- 010: Private and transactional replacement of one InBody source filename.
-- IMPORTANT: deploy only after reviewed application changes; never call this
-- function as the consent-only / anonymous demo writer.
--
-- Reprocessing the same file must not leave outdated measurements in the
-- active audit view. In the same PostgreSQL transaction, securely archive
-- the old extraction and all its rows, remove those active rows, then pass
-- the replacement through the existing validated submission function.
-- If validation, insertion or any other step fails, ALL changes roll back.
-- Archives remain private and allow manual restoration by the DB owner.

CREATE TABLE IF NOT EXISTS public.hj_replaced_audit_backups (
    old_extraction_id uuid PRIMARY KEY,
    old_extraction jsonb NOT NULL,
    old_measurements jsonb NOT NULL,
    replacement_extraction_id uuid,
    replaced_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hj_replaced_audit_backup_rows_array
      CHECK (jsonb_typeof(old_measurements) = 'array')
);

COMMENT ON TABLE public.hj_replaced_audit_backups IS
  'Private recovery copy of InBody audit extraction and measurements replaced '
  'by verified same-filename re-upload. Contains sensitive original data; '
  'no public or demo access.';

REVOKE ALL ON public.hj_replaced_audit_backups FROM PUBLIC;
REVOKE ALL ON public.hj_replaced_audit_backups
    FROM health_journey_demo_writer;

CREATE OR REPLACE FUNCTION public.hj_replace_reviewed_audit_filename(
    p_payload jsonb,
    p_confirm_replace boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_filename text;
    v_hash text;
    v_person_key text;
    v_exam timestamp;
    v_old_id uuid;
    v_new_id uuid;
    v_replaced_count integer := 0;
    v_archived_rows integer := 0;
    v_old_ids uuid[] := ARRAY[]::uuid[];
BEGIN
    IF p_confirm_replace IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Filename replacement requires explicit confirmation';
    END IF;
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object'
       OR octet_length(p_payload::text) > 2097152 THEN
        RAISE EXCEPTION 'Invalid replacement payload';
    END IF;
    v_filename := btrim(p_payload->>'filename');
    v_hash := p_payload->>'source_sha256';
    IF length(v_filename) NOT BETWEEN 1 AND 255
       OR v_hash IS NULL OR v_hash !~ '^[0-9a-f]{64}$'
       OR length(btrim(coalesce(p_payload->>'person_id',''))) NOT BETWEEN 1 AND 128
       OR length(btrim(coalesce(p_payload->>'exam_datetime',''))) NOT BETWEEN 10 AND 32
       OR jsonb_typeof(p_payload->'measurements') <> 'array'
       OR jsonb_array_length(p_payload->'measurements') NOT BETWEEN 1 AND 350
    THEN
       RAISE EXCEPTION 'Invalid replacement metadata';
    END IF;
    v_exam := (p_payload->>'exam_datetime')::timestamp;
    IF btrim(p_payload->>'person_id') ~ '^[0-9[:space:]-]+$' THEN
        v_person_key := regexp_replace(p_payload->>'person_id', '[^0-9]', '', 'g');
    ELSE
        v_person_key := upper(btrim(p_payload->>'person_id'));
    END IF;

    -- Match the lock order of the normal receipt writer (migration 007).
    PERFORM pg_advisory_xact_lock(hashtextextended('audit-file:' || lower(v_filename),0));
    PERFORM pg_advisory_xact_lock(hashtextextended('audit-sha:' || v_hash,0));
    PERFORM pg_advisory_xact_lock(hashtextextended(
      'audit-exam:' || v_person_key || ':' || v_exam::text,0
    ));

    -- A filename may not be taken over from another person, including
    -- legacy records that lack an anonymous alias. No deletion on mismatch.
    IF EXISTS (
        SELECT 1 FROM public.hj_extraction_audits e
        LEFT JOIN public.hj_person_aliases p ON e.anonymous_id = p.anonymous_id
        WHERE lower(btrim(e.filename)) = lower(v_filename)
          AND (p.normalized_person_id IS NULL
               OR p.normalized_person_id IS DISTINCT FROM v_person_key)
    ) THEN
        RAISE EXCEPTION 'Filename belongs to a different or unverified identity';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.hj_extraction_audits e
        JOIN public.hj_person_aliases p ON e.anonymous_id = p.anonymous_id
        WHERE lower(btrim(e.filename)) = lower(v_filename)
          AND p.normalized_person_id = v_person_key
    ) THEN
        RAISE EXCEPTION 'No matching reviewed filename to replace';
    END IF;

    -- Do not replace a renamed copy or silently overwrite measurements from
    -- a different source. The operation is scoped strictly to this filename.
    IF EXISTS (
        SELECT 1 FROM public.hj_extraction_audits e
        WHERE e.source_sha256 = v_hash
          AND lower(btrim(e.filename)) <> lower(v_filename)
    ) THEN
        RAISE EXCEPTION 'Uploaded content already belongs to another filename';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(p_payload->'measurements') incoming(row_value)
        JOIN public.hj_extraction_audits e ON e.exam_datetime = v_exam
        JOIN public.hj_person_aliases p ON p.anonymous_id = e.anonymous_id
        JOIN public.hj_measurement_audits m ON m.extraction_id = e.extraction_id
        WHERE p.normalized_person_id = v_person_key
          AND lower(btrim(e.filename)) <> lower(v_filename)
          AND lower(btrim(m.measurement)) =
              lower(btrim(incoming.row_value->>'measurement'))
    ) THEN
        RAISE EXCEPTION 'The examination also has measurements from another file';
    END IF;

    -- Copy sensitive old records to a private recovery table, then remove
    -- them from the ACTIVE tables. Subsequent insert reuses the source SHA.
    -- Everything occurs in the invoking transaction.
    FOR v_old_id IN
        SELECT e.extraction_id
        FROM public.hj_extraction_audits e
        JOIN public.hj_person_aliases p ON p.anonymous_id = e.anonymous_id
        WHERE lower(btrim(e.filename)) = lower(v_filename)
          AND p.normalized_person_id = v_person_key
        ORDER BY e.extraction_id FOR UPDATE OF e
    LOOP
        INSERT INTO public.hj_replaced_audit_backups
            (old_extraction_id, old_extraction, old_measurements)
        SELECT e.extraction_id, to_jsonb(e),
               COALESCE((
                  SELECT jsonb_agg(to_jsonb(m) ORDER BY m.row_number)
                  FROM public.hj_measurement_audits m
                  WHERE m.extraction_id = e.extraction_id
               ), '[]'::jsonb)
        FROM public.hj_extraction_audits e
        WHERE e.extraction_id = v_old_id;
        DELETE FROM public.hj_measurement_audits
         WHERE extraction_id = v_old_id;
        GET DIAGNOSTICS v_archived_rows = ROW_COUNT;
        v_replaced_count := v_replaced_count + v_archived_rows;
        DELETE FROM public.hj_extraction_audits
         WHERE extraction_id = v_old_id;
        v_old_ids := array_append(v_old_ids, v_old_id);
    END LOOP;

    -- Existing schema validations apply unchanged: row consistency, corrected
    -- comments, decimal syntax, provenance, source SHA and row count.
    v_new_id := public.hj_submit_reviewed_audit(p_payload);
    UPDATE public.hj_replaced_audit_backups
    SET replacement_extraction_id = v_new_id
    WHERE old_extraction_id = ANY(v_old_ids);

    RETURN jsonb_build_object(
      'status', 'replaced_filename',
      'replaced_extractions', array_length(v_old_ids, 1),
      'removed_measurements', v_replaced_count,
      'inserted_measurements', jsonb_array_length(p_payload->'measurements')
    );
END;
$$;

REVOKE ALL ON FUNCTION public.hj_replace_reviewed_audit_filename(jsonb,boolean)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.hj_replace_reviewed_audit_filename(jsonb,boolean)
  FROM health_journey_demo_writer;
GRANT EXECUTE ON FUNCTION public.hj_replace_reviewed_audit_filename(jsonb,boolean)
  TO health_journey_app, health_journey_runtime;

-- No DELETE, SELECT or archive permissions granted to demo writer.
-- No automatic data migration; existing records are unchanged until a user
-- explicitly confirms a matching filename replacement in the application.
