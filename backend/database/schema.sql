-- ============================================================
-- QuakeSense Database Schema (PostgreSQL with TimescaleDB)
-- ============================================================
-- This schema supports earthquake monitoring with ML features
-- Optimized for time-series data with TimescaleDB extension
--
-- Usage:
--   psql -U quakeuser -d quakesense -f schema.sql
-- ============================================================

-- Enable TimescaleDB extension (if available)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- MAIN SEISMIC EVENTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS seismic_events (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    server_timestamp TIMESTAMPTZ DEFAULT NOW(),
    device_id VARCHAR(100),

    -- ========================================
    -- ORIGINAL 6 FEATURES
    -- ========================================
    horizontal_accel REAL,              -- Horizontal acceleration (m/s²)
    total_accel REAL,                   -- Total acceleration magnitude (m/s²)
    sound_level INTEGER,                -- Sound sensor reading (0-4095)
    sound_correlated BOOLEAN,           -- Whether sound correlates with vibration

    -- ========================================
    -- 12 NEW ENHANCED FEATURES
    -- ========================================
    -- Acceleration Components (4 features)
    vertical_accel REAL,                -- Vertical acceleration component (m/s²)
    x_accel REAL,                       -- X-axis acceleration (m/s²)
    y_accel REAL,                       -- Y-axis acceleration (m/s²)
    z_accel REAL,                       -- Z-axis acceleration (m/s²)

    -- Frequency Domain (3 features)
    peak_ground_acceleration REAL,      -- Peak ground acceleration (PGA) (m/s²)
    frequency_dominant REAL,            -- Dominant frequency (Hz)
    frequency_mean REAL,                -- Mean frequency content (Hz)

    -- Temporal Features (3 features)
    duration_ms INTEGER,                -- Event duration (milliseconds)
    wave_arrival_pattern VARCHAR(50),   -- Wave pattern (p_then_s, simultaneous, etc.)
    temporal_variance REAL,             -- Variance over time window

    -- Wave Detection (2 features)
    p_wave_detected BOOLEAN,            -- Primary wave detected
    s_wave_detected BOOLEAN,            -- Secondary wave detected

    -- ========================================
    -- AI CLASSIFICATION RESULTS
    -- ========================================
    ai_classification VARCHAR(50),      -- 'genuine_earthquake', 'false_alarm', 'uncertain'
    ai_confidence REAL,                 -- Confidence score (0-1)
    ai_reasoning TEXT,                  -- Explanation of classification
    ai_model_version VARCHAR(20),       -- Model version used

    -- ========================================
    -- SEVERITY & ALERTING
    -- ========================================
    severity VARCHAR(20),               -- 'low', 'medium', 'high', 'critical'
    telegram_sent BOOLEAN DEFAULT FALSE, -- Whether Telegram alert was sent

    -- ========================================
    -- VERIFICATION & TRAINING
    -- ========================================
    is_verified BOOLEAN DEFAULT FALSE,  -- Whether event has been verified
    verified_magnitude REAL,            -- Verified magnitude (if available)
    usgs_event_id VARCHAR(100),         -- USGS event ID (for correlation)
    phivolcs_event_id VARCHAR(100)      -- PHIVOLCS event ID (for correlation)
);

-- ========================================
-- INDEXES FOR PERFORMANCE
-- ========================================
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON seismic_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_server_timestamp ON seismic_events (server_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_device ON seismic_events (device_id);
CREATE INDEX IF NOT EXISTS idx_events_classification ON seismic_events (ai_classification);
CREATE INDEX IF NOT EXISTS idx_events_verified ON seismic_events (is_verified);
CREATE INDEX IF NOT EXISTS idx_events_severity ON seismic_events (severity);

-- ========================================
-- CONVERT TO TIMESCALEDB HYPERTABLE
-- ========================================
-- Automatically partitions by time for efficient time-series queries
-- Only run if TimescaleDB extension is installed
SELECT create_hypertable('seismic_events', 'timestamp', if_not_exists => TRUE);

-- Enable automatic compression (optional, for older data)
ALTER TABLE seismic_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id'
);

-- Add compression policy: compress data older than 30 days
SELECT add_compression_policy('seismic_events', INTERVAL '30 days');

-- ============================================================
-- TRAINING DATASETS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS training_datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    source VARCHAR(50),                 -- 'usgs', 'phivolcs', 'synthetic', 'manual'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sample_count INTEGER,
    genuine_count INTEGER,
    false_alarm_count INTEGER,
    version VARCHAR(20)
);

-- ============================================================
-- TRAINING SAMPLES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS training_samples (
    id BIGSERIAL PRIMARY KEY,
    dataset_id INTEGER REFERENCES training_datasets(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES seismic_events(id) ON DELETE SET NULL,
    label VARCHAR(20) NOT NULL,         -- 'genuine', 'false_alarm'
    confidence REAL,                    -- Confidence in label (0-1)
    notes TEXT,                         -- Additional notes or JSON data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_samples_dataset ON training_samples (dataset_id);
CREATE INDEX IF NOT EXISTS idx_training_samples_label ON training_samples (label);

-- ============================================================
-- MODEL VERSIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS model_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,
    algorithm VARCHAR(50),              -- 'isolation_forest', 'random_forest', 'svm', etc.
    training_samples INTEGER,
    accuracy REAL,
    precision_score REAL,
    recall_score REAL,
    f1_score REAL,
    hyperparameters JSONB,              -- JSON of hyperparameters
    trained_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE,    -- Which model is currently deployed
    model_path VARCHAR(500)             -- Path to saved model file
);

CREATE INDEX IF NOT EXISTS idx_model_versions_active ON model_versions (is_active);

-- ============================================================
-- DEVICE REGISTRY TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) UNIQUE NOT NULL,
    location VARCHAR(200),
    latitude REAL,
    longitude REAL,
    installed_at TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    firmware_version VARCHAR(50),
    calibration_offset REAL,           -- Sensor calibration offset
    metadata JSONB                      -- Additional device metadata
);

CREATE INDEX IF NOT EXISTS idx_devices_active ON devices (is_active);
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices (last_seen DESC);

-- ============================================================
-- ALERT HISTORY TABLE (Optional)
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_history (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT REFERENCES seismic_events(id) ON DELETE CASCADE,
    alert_type VARCHAR(50),             -- 'telegram', 'email', 'sms', etc.
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    recipient VARCHAR(200),
    success BOOLEAN,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_alert_history_event ON alert_history (event_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_sent_at ON alert_history (sent_at DESC);

-- ============================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================

-- View: Recent genuine earthquakes only
CREATE OR REPLACE VIEW recent_genuine_earthquakes AS
SELECT *
FROM seismic_events
WHERE ai_classification = 'genuine_earthquake'
ORDER BY timestamp DESC
LIMIT 100;

-- View: Daily statistics
CREATE OR REPLACE VIEW daily_statistics AS
SELECT
    DATE(timestamp) as date,
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE ai_classification = 'genuine_earthquake') as genuine_count,
    COUNT(*) FILTER (WHERE ai_classification = 'false_alarm') as false_alarm_count,
    AVG(horizontal_accel) as avg_magnitude,
    MAX(horizontal_accel) as max_magnitude
FROM seismic_events
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- View: Device status
CREATE OR REPLACE VIEW device_status AS
SELECT
    d.device_id,
    d.location,
    d.is_active,
    d.last_seen,
    COUNT(e.id) as event_count,
    MAX(e.timestamp) as last_event
FROM devices d
LEFT JOIN seismic_events e ON d.device_id = e.device_id
GROUP BY d.id, d.device_id, d.location, d.is_active, d.last_seen;

-- ============================================================
-- FUNCTIONS FOR DATA RETENTION
-- ============================================================

-- Function to delete old events (for data retention policy)
CREATE OR REPLACE FUNCTION delete_old_events(retention_days INTEGER)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM seismic_events
    WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL
    AND is_verified = FALSE;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- INITIAL DATA (Optional)
-- ============================================================

-- Insert default model version (untrained)
INSERT INTO model_versions (version, algorithm, is_active, trained_at)
VALUES ('v0.0.0-untrained', 'isolation_forest', TRUE, NOW())
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- GRANTS (Update with your database user)
-- ============================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO quakeuser;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO quakeuser;

-- ============================================================
-- COMMENTS
-- ============================================================
COMMENT ON TABLE seismic_events IS 'Main table storing all seismic events with 18 ML features';
COMMENT ON TABLE training_samples IS 'Labeled training data for ML model training';
COMMENT ON TABLE model_versions IS 'ML model version tracking and performance metrics';
COMMENT ON TABLE devices IS 'Registry of earthquake sensor devices';

COMMENT ON COLUMN seismic_events.horizontal_accel IS 'Horizontal acceleration in m/s² (primary magnitude indicator)';
COMMENT ON COLUMN seismic_events.frequency_dominant IS 'Dominant frequency in Hz (earthquakes: 1-10 Hz, false alarms: >10 Hz)';
COMMENT ON COLUMN seismic_events.p_wave_detected IS 'Primary compression wave detection (arrives first, ~6 km/s)';
COMMENT ON COLUMN seismic_events.s_wave_detected IS 'Secondary shear wave detection (arrives later, ~3.5 km/s)';

-- ============================================================
-- MAINTENANCE QUERIES
-- ============================================================

-- Check table sizes
-- SELECT
--     schemaname,
--     tablename,
--     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check TimescaleDB hypertable info
-- SELECT * FROM timescaledb_information.hypertables;

-- Check compression status
-- SELECT * FROM timescaledb_information.compression_settings;

-- ============================================================
-- DONE
-- ============================================================
-- Schema initialization complete!
-- Next steps:
--   1. Configure .env with database credentials
--   2. Run: python scripts/init_database.py
--   3. Start backend: python quake.py
-- ============================================================
