-- 008: Private FitNotes training log imports (additive; no InBody schema changes).
-- No public/anonymous reader and no anonymous demo writer permissions.
CREATE TABLE IF NOT EXISTS public.hj_training_imports (
    import_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_key text NOT NULL CHECK (length(owner_key) BETWEEN 1 AND 128),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    filename text NOT NULL CHECK (length(filename) BETWEEN 1 AND 255),
    row_count integer NOT NULL CHECK (row_count BETWEEN 1 AND 100000),
    inserted_count integer NOT NULL DEFAULT 0 CHECK (inserted_count >= 0),
    updated_count integer NOT NULL DEFAULT 0 CHECK (updated_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_key, source_sha256)
);

CREATE TABLE IF NOT EXISTS public.hj_training_sets (
    set_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_key text NOT NULL CHECK (length(owner_key) BETWEEN 1 AND 128),
    workout_date date NOT NULL,
    exercise text NOT NULL CHECK (length(exercise) BETWEEN 1 AND 200),
    exercise_key text NOT NULL CHECK (length(exercise_key) BETWEEN 1 AND 200),
    category text NULL CHECK (length(category) <= 100),
    set_number integer NOT NULL CHECK (set_number > 0),
    weight numeric NULL,
    weight_unit text NULL CHECK (length(weight_unit) <= 24),
    reps numeric NULL,
    distance numeric NULL,
    distance_unit text NULL CHECK (length(distance_unit) <= 24),
    duration_seconds integer NULL CHECK (duration_seconds >= 0),
    comment text NULL CHECK (length(comment) <= 2000),
    first_import_id uuid NOT NULL REFERENCES public.hj_training_imports(import_id),
    last_import_id uuid NOT NULL REFERENCES public.hj_training_imports(import_id),
    first_row_number integer NOT NULL CHECK (first_row_number > 1),
    last_row_number integer NOT NULL CHECK (last_row_number > 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hj_training_one_set_per_slot
      UNIQUE (owner_key, workout_date, exercise_key, set_number)
);

CREATE INDEX IF NOT EXISTS hj_training_owner_date
    ON public.hj_training_sets (owner_key, workout_date DESC);
CREATE INDEX IF NOT EXISTS hj_training_owner_exercise_date
    ON public.hj_training_sets (owner_key, exercise_key, workout_date DESC);

REVOKE ALL ON public.hj_training_imports FROM PUBLIC;
REVOKE ALL ON public.hj_training_sets FROM PUBLIC;
REVOKE ALL ON public.hj_training_imports FROM health_journey_public, health_journey_demo_writer;
REVOKE ALL ON public.hj_training_sets FROM health_journey_public, health_journey_demo_writer;
GRANT SELECT, INSERT, UPDATE ON public.hj_training_imports
    TO health_journey_app, health_journey_runtime;
GRANT SELECT, INSERT, UPDATE ON public.hj_training_sets
    TO health_journey_app, health_journey_runtime;
