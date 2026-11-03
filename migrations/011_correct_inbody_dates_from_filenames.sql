-- 011: Backfill stored InBody exam timestamps from filename token.
-- The first '_' is immediately followed by YYYYMMDDHHMMSS.
--
-- This is a DATA CORRECTION, separate from the optional re-upload feature.
-- A backup is inserted BEFORE any update, preserving the old timestamp.
-- All operations MUST run as one transaction. PostgreSQL DO is atomic.
-- No measurements, original Gemini responses or patient identifiers change.

CREATE TABLE IF NOT EXISTS public.hj_exam_datetime_repair_history (
  extraction_id uuid PRIMARY KEY,
  filename text NOT NULL,
  original_exam_datetime timestamp NOT NULL,
  corrected_exam_datetime timestamp NOT NULL,
  correction_source text NOT NULL DEFAULT 'filename_first_underscore_YYYYMMDDHHMMSS',
  repaired_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.hj_exam_datetime_repair_history IS
  'Private date correction log: original and new exam_datetime derived from the '
  'first 14-digit token after the first underscore in filename. Never public.';

REVOKE ALL ON public.hj_exam_datetime_repair_history FROM PUBLIC;
REVOKE ALL ON public.hj_exam_datetime_repair_history
  FROM health_journey_demo_writer, health_journey_runtime;

DO $repair$
DECLARE
  v_row record;
  v_token text;
  v_corrected timestamp;
  v_fixed integer := 0;
BEGIN
  FOR v_row IN
    SELECT e.extraction_id, e.filename, e.exam_datetime, e.anonymous_id
    FROM public.hj_extraction_audits e
    ORDER BY e.extraction_id
    FOR UPDATE
  LOOP
    v_token := substring(v_row.filename FROM
      '^[^_]+_([0-9]{14})(?:[._-]|$)');
    -- Preserve legacy filenames without this explicit contract.
    IF v_token IS NULL THEN
      CONTINUE;
    END IF;
    v_corrected := to_timestamp(v_token, 'YYYYMMDDHH24MISS')::timestamp;
    -- PostgreSQL may normalize nonsensical dates: reject those rather
    -- than silently assigning a different exam time.
    IF to_char(v_corrected, 'YYYYMMDDHH24MISS') <> v_token THEN
      RAISE EXCEPTION 'Invalid YYYYMMDDHHMMSS date in source filename';
    END IF;
    IF v_row.exam_datetime = v_corrected THEN
      CONTINUE;
    END IF;

    -- Avoid merging independent exams: a new timestamp must not overlap
    -- another active source of the SAME owner for the same measurement.
    IF EXISTS (
      SELECT 1
      FROM public.hj_extraction_audits e
      JOIN public.hj_measurement_audits other_m
        ON other_m.extraction_id = e.extraction_id
      JOIN public.hj_measurement_audits this_m
        ON this_m.extraction_id = v_row.extraction_id
      WHERE e.extraction_id <> v_row.extraction_id
        AND e.anonymous_id IS NOT DISTINCT FROM v_row.anonymous_id
        AND e.exam_datetime = v_corrected
        AND lower(btrim(other_m.measurement)) = lower(btrim(this_m.measurement))
    ) THEN
      RAISE EXCEPTION 'Conflicting exam exists at filename timestamp';
    END IF;

    INSERT INTO public.hj_exam_datetime_repair_history
      (extraction_id, filename, original_exam_datetime, corrected_exam_datetime)
    VALUES
      (v_row.extraction_id, v_row.filename, v_row.exam_datetime, v_corrected)
    ON CONFLICT (extraction_id) DO NOTHING;
    -- An earlier repair is never silently overwritten on reruns.
    IF NOT EXISTS (
      SELECT 1 FROM public.hj_exam_datetime_repair_history h
      WHERE h.extraction_id = v_row.extraction_id
        AND h.original_exam_datetime = v_row.exam_datetime
        AND h.corrected_exam_datetime = v_corrected
    ) THEN
      RAISE EXCEPTION 'Unexpected previous correction for extraction';
    END IF;
    UPDATE public.hj_extraction_audits
      SET exam_datetime = v_corrected
      WHERE extraction_id = v_row.extraction_id;
    v_fixed := v_fixed + 1;
  END LOOP;
  RAISE NOTICE 'InBody filename timestamps corrected: %', v_fixed;
END
$repair$;

-- To inspect without personal data:
-- SELECT count(*) FROM public.hj_exam_datetime_repair_history;
-- To restore one correction, only an authorized DB owner should use the
-- original timestamp in hj_exam_datetime_repair_history inside a transaction.
