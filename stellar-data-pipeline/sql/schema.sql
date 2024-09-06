-- PostgreSQL schema for the stellar data pipeline.
-- Run once to initialize or use Pipeline.ensure_schema() for automatic creation.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS exoplanets (
    pl_name                VARCHAR(255) PRIMARY KEY,
    hostname               VARCHAR(255) NOT NULL,
    discovery_method       VARCHAR(100),
    disc_year              INTEGER,
    orbital_period_days    DOUBLE PRECISION,
    radius_earth           DOUBLE PRECISION,
    radius_jupiter         DOUBLE PRECISION,
    mass_earth             DOUBLE PRECISION,
    mass_jupiter           DOUBLE PRECISION,
    equilibrium_temp_k     DOUBLE PRECISION,
    stellar_teff_k         DOUBLE PRECISION,
    stellar_radius_solar   DOUBLE PRECISION,
    stellar_mass_solar     DOUBLE PRECISION,
    distance_pc            DOUBLE PRECISION,
    is_habitable_zone      BOOLEAN DEFAULT FALSE,
    run_id                 UUID,
    ingested_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exoplanets_hostname ON exoplanets (hostname);
CREATE INDEX IF NOT EXISTS idx_exoplanets_discovery_method ON exoplanets (discovery_method);
CREATE INDEX IF NOT EXISTS idx_exoplanets_habitable ON exoplanets (is_habitable_zone) WHERE is_habitable_zone = TRUE;
CREATE INDEX IF NOT EXISTS idx_exoplanets_run_id ON exoplanets (run_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id                      UUID PRIMARY KEY,
    started_at                  TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at                TIMESTAMP WITH TIME ZONE,
    status                      VARCHAR(50) NOT NULL DEFAULT 'running',
    records_extracted           INTEGER DEFAULT 0,
    records_validated           INTEGER DEFAULT 0,
    records_failed_validation   INTEGER DEFAULT 0,
    records_transformed         INTEGER DEFAULT 0,
    records_loaded              INTEGER DEFAULT 0,
    error_message               TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs (status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs (started_at DESC);
