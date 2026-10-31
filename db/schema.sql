-- Health Journey / InBody Hub: initial Neon PostgreSQL schema
-- Applied to Neon project health-journey / database health_journey on 2026-10-31.
-- Only reviewed examinations belong in these tables; no original PDF/JPG/PNG
-- or OCR free-text is persisted. Source files are tracked by SHA-256.
-- For future schema updates use Alembic migrations (do not manually drop tables).

CREATE TABLE IF NOT EXISTS hj_persons (
 person_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 id_persona VARCHAR(128) NOT NULL,
 source_namespace VARCHAR(128) NOT NULL DEFAULT 'inbody_unverified',
 birth_date DATE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (source_namespace, id_persona)
);

CREATE TABLE IF NOT EXISTS hj_exams (
 exam_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 person_uuid UUID NOT NULL REFERENCES hj_persons(person_uuid),
 source_sha256 CHAR(64) NOT NULL UNIQUE,
 modelo_inbody VARCHAR(128),
 machine_identifier VARCHAR(128),
 exam_timestamp TIMESTAMP WITHOUT TIME ZONE,
 timezone_name VARCHAR(64),
 edad INTEGER CHECK (edad BETWEEN 0 AND 120),
 age_source VARCHAR(64),
 idioma_reporte VARCHAR(7) NOT NULL DEFAULT 'UNKNOWN'
   CHECK (idioma_reporte IN ('ES','EN','UNKNOWN')),
 language_basis VARCHAR(40) NOT NULL DEFAULT 'unverified',
 source_type VARCHAR(12) NOT NULL
   CHECK (source_type IN ('pdf','jpg','jpeg','png')),
 confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hj_measurements (
 measurement_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 exam_uuid UUID NOT NULL REFERENCES hj_exams(exam_uuid) ON DELETE CASCADE,
 row_number INTEGER NOT NULL CHECK (row_number > 0),
 variable_medida VARCHAR(180) NOT NULL,
 original_label TEXT NOT NULL,
 categoria VARCHAR(100),
 dimension VARCHAR(100),
 segmento VARCHAR(64),
 frecuencia_khz NUMERIC(10,3),
 unidad_medida VARCHAR(64),
 valor_medida NUMERIC(18,6),
 pagina INTEGER CHECK (pagina > 0),
 extraction_source VARCHAR(64),
 confirmation_status VARCHAR(16) NOT NULL DEFAULT 'confirmed'
   CHECK (confirmation_status IN ('confirmed','needs_review')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (exam_uuid, row_number)
);

CREATE TABLE IF NOT EXISTS hj_measurement_catalog (
 canonical_code VARCHAR(180) PRIMARY KEY,
 display_label_es VARCHAR(255),
 display_label_en VARCHAR(255),
 categoria VARCHAR(100),
 dimension VARCHAR(100),
 canonical_unit VARCHAR(64),
 comparability_rule TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hj_exams_person_time
 ON hj_exams(person_uuid, exam_timestamp);

CREATE INDEX IF NOT EXISTS idx_hj_measurements_metric
 ON hj_measurements(variable_medida, segmento, unidad_medida);

-- Seven-column reporting interface; language and provenance are in hj_exams.
CREATE OR REPLACE VIEW hj_measurements_long AS
SELECT p.id_persona, e.modelo_inbody, e.exam_timestamp AS "timestamp",
       m.variable_medida, m.unidad_medida, m.valor_medida, e.edad
FROM hj_measurements m
JOIN hj_exams e ON m.exam_uuid=e.exam_uuid
JOIN hj_persons p ON e.person_uuid=p.person_uuid;
