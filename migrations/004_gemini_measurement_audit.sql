-- Apply manually in the private Neon database before enabling Gemini audit save.
CREATE TABLE IF NOT EXISTS hj_extraction_audits (
  extraction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_sha256 text NOT NULL UNIQUE,
  filename text NOT NULL,
  person_id text NOT NULL,
  exam_datetime timestamp NOT NULL,
  age integer CHECK (age BETWEEN 0 AND 120),
  model_name text NOT NULL,
  raw_response jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hj_measurement_audits (
  extraction_id uuid NOT NULL REFERENCES hj_extraction_audits(extraction_id) ON DELETE RESTRICT,
  row_number integer NOT NULL CHECK (row_number > 0),
  section text NOT NULL,
  measurement text NOT NULL,
  original_section text NOT NULL,
  original_measurement text NOT NULL,
  original_value text NOT NULL,
  original_unit text,
  final_value text NOT NULL,
  final_unit text,
  was_corrected boolean NOT NULL,
  correction_comment text,
  reviewed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (extraction_id, row_number),
  CONSTRAINT correction_comment_required CHECK (
    NOT was_corrected OR NULLIF(btrim(correction_comment), '') IS NOT NULL
  )
);
CREATE INDEX IF NOT EXISTS hj_measurement_audits_review_idx
  ON hj_measurement_audits(was_corrected, reviewed_at DESC);
-- Store patient identifiers and raw Gemini output ONLY in this private schema.
-- Grant access exclusively to the authenticated application DB role.