-- 006: App-local master-demo account. No PostgreSQL LOGIN role is created.
-- Credentials are stored as one-way PBKDF2 password verifiers.
-- Never insert passwords or plaintext setup tokens into this migration.
CREATE TABLE IF NOT EXISTS public.hj_app_accounts (
    username text PRIMARY KEY CHECK (username ~ '^[a-z0-9-]{3,40}$'),
    password_hash text NOT NULL CHECK (password_hash LIKE 'pbkdf2_sha256$%'),
    role text NOT NULL CHECK (role IN ('master_demo')),
    enabled boolean NOT NULL DEFAULT false,
    failed_attempts integer NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    locked_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz,
    password_changed_at timestamptz
);
-- Do not grant access to public/demo writer even if other tables are writable.
REVOKE ALL ON TABLE public.hj_app_accounts FROM PUBLIC;
REVOKE ALL ON TABLE public.hj_app_accounts FROM health_journey_demo_writer;
REVOKE ALL ON TABLE public.hj_app_accounts FROM health_journey_public;
-- The private application roles may read the password verifier and update
-- only login security fields; never grant these permissions to demo/public.
GRANT SELECT ON TABLE public.hj_app_accounts
    TO health_journey_app, health_journey_runtime;
GRANT UPDATE (password_hash, failed_attempts, locked_until,
              last_login_at, password_changed_at)
    ON TABLE public.hj_app_accounts
    TO health_journey_app, health_journey_runtime;
-- A single app account is provisioned separately by an authorized administrator.
-- Disable the account by UPDATE enabled=false to revoke access.
