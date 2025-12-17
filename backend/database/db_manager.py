"""
Database Manager for QuakeSense
Provides abstraction layer for PostgreSQL and SQLite databases
Handles seismic event storage, training data, and model versioning
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

# Try importing PostgreSQL driver, fallback to SQLite
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("WARNING: psycopg2 not installed. Using SQLite fallback.")

import sqlite3


class DatabaseManager:
    """
    Database abstraction layer supporting PostgreSQL and SQLite
    """

    def __init__(self, db_type=None):
        """
        Initialize database connection

        Args:
            db_type: 'postgresql' or 'sqlite'. If None, reads from environment.
        """
        self.db_type = db_type or os.environ.get('DATABASE_TYPE', 'sqlite')
        self.connection = None
        self.cursor = None

        # Validate database type
        if self.db_type == 'postgresql' and not POSTGRESQL_AVAILABLE:
            print("WARNING: PostgreSQL requested but psycopg2 not installed. Falling back to SQLite.")
            self.db_type = 'sqlite'

        self._connect()
        self._initialize_schema()

    def _connect(self):
        """Establish database connection"""
        if self.db_type == 'postgresql':
            self._connect_postgresql()
        else:
            self._connect_sqlite()

    def _connect_postgresql(self):
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=os.environ.get('DATABASE_HOST', 'localhost'),
                port=os.environ.get('DATABASE_PORT', '5432'),
                database=os.environ.get('DATABASE_NAME', 'quakesense'),
                user=os.environ.get('DATABASE_USER', 'quakeuser'),
                password=os.environ.get('DATABASE_PASSWORD', '')
            )
            self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            print(f"[OK] Connected to PostgreSQL database: {os.environ.get('DATABASE_NAME', 'quakesense')}")
        except Exception as e:
            print(f"[ERROR] PostgreSQL connection failed: {e}")
            print("   Falling back to SQLite...")
            self.db_type = 'sqlite'
            self._connect_sqlite()

    def _connect_sqlite(self):
        """Connect to SQLite database"""
        db_path = os.environ.get('DATABASE_PATH', 'quakesense.db')
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row  # Return dict-like rows
        self.cursor = self.connection.cursor()
        print(f"[OK] Connected to SQLite database: {db_path}")

    def _initialize_schema(self):
        """Create tables if they don't exist"""
        if self.db_type == 'postgresql':
            self._initialize_postgresql_schema()
        else:
            self._initialize_sqlite_schema()

    def _initialize_postgresql_schema(self):
        """Initialize PostgreSQL schema"""
        schema_sql = """
        -- Main seismic events table
        CREATE TABLE IF NOT EXISTS seismic_events (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            server_timestamp TIMESTAMPTZ DEFAULT NOW(),
            device_id VARCHAR(100),

            -- Original 6 features
            horizontal_accel REAL,
            total_accel REAL,
            sound_level INTEGER,
            sound_correlated BOOLEAN,

            -- 12 NEW features
            vertical_accel REAL,
            x_accel REAL,
            y_accel REAL,
            z_accel REAL,
            peak_ground_acceleration REAL,
            frequency_dominant REAL,
            frequency_mean REAL,
            duration_ms INTEGER,
            wave_arrival_pattern VARCHAR(50),
            p_wave_detected BOOLEAN,
            s_wave_detected BOOLEAN,
            temporal_variance REAL,

            -- AI results
            ai_classification VARCHAR(50),
            ai_confidence REAL,
            ai_reasoning TEXT,
            severity VARCHAR(20),
            telegram_sent BOOLEAN DEFAULT FALSE,

            -- Verification (for training)
            is_verified BOOLEAN DEFAULT FALSE,
            verified_magnitude REAL,
            usgs_event_id VARCHAR(100)
        );

        -- Create indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON seismic_events (timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_events_device ON seismic_events (device_id);
        CREATE INDEX IF NOT EXISTS idx_events_classification ON seismic_events (ai_classification);
        CREATE INDEX IF NOT EXISTS idx_events_verified ON seismic_events (is_verified);

        -- Training datasets table
        CREATE TABLE IF NOT EXISTS training_datasets (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            source VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            sample_count INTEGER,
            genuine_count INTEGER,
            false_alarm_count INTEGER,
            version VARCHAR(20)
        );

        -- Training samples table
        CREATE TABLE IF NOT EXISTS training_samples (
            id BIGSERIAL PRIMARY KEY,
            dataset_id INTEGER REFERENCES training_datasets(id),
            event_id BIGINT REFERENCES seismic_events(id),
            label VARCHAR(20) NOT NULL,
            confidence REAL,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Model versions table
        CREATE TABLE IF NOT EXISTS model_versions (
            id SERIAL PRIMARY KEY,
            version VARCHAR(20) NOT NULL UNIQUE,
            algorithm VARCHAR(50),
            training_samples INTEGER,
            accuracy REAL,
            precision_score REAL,
            recall_score REAL,
            f1_score REAL,
            hyperparameters JSONB,
            trained_at TIMESTAMPTZ DEFAULT NOW(),
            is_active BOOLEAN DEFAULT FALSE,
            model_path VARCHAR(500)
        );

        -- Device registry table
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
            metadata JSONB
        );
        """

        try:
            self.cursor.execute(schema_sql)
            self.connection.commit()
            print("[OK] PostgreSQL schema initialized")
        except Exception as e:
            print(f"[WARNING] Schema initialization warning: {e}")
            self.connection.rollback()

    def _initialize_sqlite_schema(self):
        """Initialize SQLite schema"""
        schema_sql = """
        -- Main seismic events table
        CREATE TABLE IF NOT EXISTS seismic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            server_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            device_id TEXT,

            -- Original 6 features
            horizontal_accel REAL,
            total_accel REAL,
            sound_level INTEGER,
            sound_correlated INTEGER,

            -- 12 NEW features
            vertical_accel REAL,
            x_accel REAL,
            y_accel REAL,
            z_accel REAL,
            peak_ground_acceleration REAL,
            frequency_dominant REAL,
            frequency_mean REAL,
            duration_ms INTEGER,
            wave_arrival_pattern TEXT,
            p_wave_detected INTEGER,
            s_wave_detected INTEGER,
            temporal_variance REAL,

            -- AI results
            ai_classification TEXT,
            ai_confidence REAL,
            ai_reasoning TEXT,
            severity TEXT,
            telegram_sent INTEGER DEFAULT 0,

            -- Verification (for training)
            is_verified INTEGER DEFAULT 0,
            verified_magnitude REAL,
            usgs_event_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON seismic_events (timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_events_device ON seismic_events (device_id);
        CREATE INDEX IF NOT EXISTS idx_events_classification ON seismic_events (ai_classification);
        """

        try:
            self.cursor.executescript(schema_sql)
            self.connection.commit()
            print("[OK] SQLite schema initialized")
        except Exception as e:
            print(f"[WARNING] Schema initialization warning: {e}")

    def insert_event(self, event_data: Dict, ai_result: Dict, severity: str) -> int:
        """
        Insert a seismic event into the database

        Args:
            event_data: Raw sensor data from Arduino
            ai_result: AI classification result
            severity: Severity level (low/medium/high/critical)

        Returns:
            event_id: Database ID of inserted event
        """
        # Convert ESP32 millis timestamp to ISO format
        if 'timestamp' in event_data:
            # ESP32 sends millis() - convert to current time for now
            # In production, should sync ESP32 time with NTP
            timestamp = datetime.now().isoformat()
        else:
            timestamp = datetime.now().isoformat()

        if self.db_type == 'postgresql':
            sql = """
            INSERT INTO seismic_events (
                timestamp, device_id,
                horizontal_accel, total_accel, sound_level, sound_correlated,
                vertical_accel, x_accel, y_accel, z_accel,
                peak_ground_acceleration, frequency_dominant, frequency_mean,
                duration_ms, wave_arrival_pattern, p_wave_detected, s_wave_detected,
                temporal_variance, ai_classification, ai_confidence, ai_reasoning, severity
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
            """
        else:
            sql = """
            INSERT INTO seismic_events (
                timestamp, device_id,
                horizontal_accel, total_accel, sound_level, sound_correlated,
                vertical_accel, x_accel, y_accel, z_accel,
                peak_ground_acceleration, frequency_dominant, frequency_mean,
                duration_ms, wave_arrival_pattern, p_wave_detected, s_wave_detected,
                temporal_variance, ai_classification, ai_confidence, ai_reasoning, severity
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """

        values = (
            timestamp,
            event_data.get('device_id', 'Unknown'),
            event_data.get('horizontal_accel'),
            event_data.get('total_accel'),
            event_data.get('sound_level'),
            1 if event_data.get('sound_correlated') else 0,
            event_data.get('vertical_accel'),
            event_data.get('x_accel'),
            event_data.get('y_accel'),
            event_data.get('z_accel'),
            event_data.get('peak_ground_acceleration'),
            event_data.get('frequency_dominant'),
            event_data.get('frequency_mean'),
            event_data.get('duration_ms'),
            event_data.get('wave_arrival_pattern'),
            1 if event_data.get('p_wave_detected') else 0,
            1 if event_data.get('s_wave_detected') else 0,
            event_data.get('temporal_variance'),
            ai_result.get('classification'),
            ai_result.get('confidence'),
            ai_result.get('reasoning'),
            severity
        )

        try:
            self.cursor.execute(sql, values)
            self.connection.commit()

            if self.db_type == 'postgresql':
                event_id = self.cursor.fetchone()['id']
            else:
                event_id = self.cursor.lastrowid

            return event_id
        except Exception as e:
            print(f"[ERROR] Error inserting event: {e}")
            self.connection.rollback()
            return -1

    def get_recent_events(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Retrieve recent seismic events

        Args:
            limit: Maximum number of events to return
            offset: Number of events to skip (for pagination)

        Returns:
            List of event dictionaries
        """
        if self.db_type == 'postgresql':
            sql = """
            SELECT * FROM seismic_events
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
            """
            self.cursor.execute(sql, (limit, offset))
        else:
            sql = """
            SELECT * FROM seismic_events
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """
            self.cursor.execute(sql, (limit, offset))

        rows = self.cursor.fetchall()

        # Convert to list of dicts
        events = []
        for row in rows:
            event = dict(row)
            # Convert boolean fields for SQLite
            if self.db_type == 'sqlite':
                event['sound_correlated'] = bool(event.get('sound_correlated', 0))
                event['p_wave_detected'] = bool(event.get('p_wave_detected', 0))
                event['s_wave_detected'] = bool(event.get('s_wave_detected', 0))
                event['telegram_sent'] = bool(event.get('telegram_sent', 0))
            events.append(event)

        return events

    def get_aggregate_statistics(self) -> Dict:
        """
        Calculate aggregate statistics for dashboard

        Returns:
            Dictionary with stats (total, today, false_alarms, accuracy)
        """
        # Total events
        self.cursor.execute("SELECT COUNT(*) as count FROM seismic_events")
        total = self.cursor.fetchone()['count']

        # Today's events
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        if self.db_type == 'postgresql':
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM seismic_events WHERE timestamp >= %s",
                (today_start,)
            )
        else:
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM seismic_events WHERE timestamp >= ?",
                (today_start,)
            )
        today = self.cursor.fetchone()['count']

        # False alarms
        if self.db_type == 'postgresql':
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM seismic_events WHERE ai_classification = %s",
                ('false_alarm',)
            )
        else:
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM seismic_events WHERE ai_classification = ?",
                ('false_alarm',)
            )
        false_alarms = self.cursor.fetchone()['count']

        # Calculate accuracy
        accuracy = ((total - false_alarms) / total * 100) if total > 0 else 0

        return {
            'total': total,
            'today': today,
            'false_alarms': false_alarms,
            'accuracy': round(accuracy, 1)
        }

    def get_events_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Get events within a date range

        Args:
            start_date: ISO format date string
            end_date: ISO format date string

        Returns:
            List of events
        """
        if self.db_type == 'postgresql':
            sql = """
            SELECT * FROM seismic_events
            WHERE timestamp BETWEEN %s AND %s
            ORDER BY timestamp DESC
            """
            self.cursor.execute(sql, (start_date, end_date))
        else:
            sql = """
            SELECT * FROM seismic_events
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
            """
            self.cursor.execute(sql, (start_date, end_date))

        return [dict(row) for row in self.cursor.fetchall()]

    def save_training_sample(self, event_data: Dict, label: str, dataset_id: Optional[int] = None) -> int:
        """
        Save a labeled training sample

        Args:
            event_data: Event features and metadata
            label: 'genuine' or 'false_alarm'
            dataset_id: Optional dataset ID to associate with

        Returns:
            sample_id: Database ID of the training sample
        """
        # For now, store as JSON in notes field
        # In production, should store properly normalized data
        if self.db_type == 'postgresql':
            sql = """
            INSERT INTO training_samples (dataset_id, label, notes)
            VALUES (%s, %s, %s)
            RETURNING id
            """
            self.cursor.execute(sql, (dataset_id, label, json.dumps(event_data)))
            sample_id = self.cursor.fetchone()['id']
        else:
            sql = """
            INSERT INTO training_samples (dataset_id, label, notes)
            VALUES (?, ?, ?)
            """
            self.cursor.execute(sql, (dataset_id, label, json.dumps(event_data)))
            sample_id = self.cursor.lastrowid

        self.connection.commit()
        return sample_id

    def update_device_last_seen(self, device_id: str):
        """Update the last_seen timestamp for a device"""
        if self.db_type == 'postgresql':
            sql = """
            INSERT INTO devices (device_id, last_seen, is_active)
            VALUES (%s, NOW(), TRUE)
            ON CONFLICT (device_id)
            DO UPDATE SET last_seen = NOW(), is_active = TRUE
            """
            self.cursor.execute(sql, (device_id,))
        else:
            # SQLite doesn't have UPSERT in older versions, so use INSERT OR REPLACE
            sql = """
            INSERT OR REPLACE INTO devices (device_id, last_seen, is_active)
            VALUES (?, datetime('now'), 1)
            """
            self.cursor.execute(sql, (device_id,))

        self.connection.commit()

    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        print("[OK] Database connection closed")

    def __del__(self):
        """Cleanup on object destruction"""
        try:
            self.close()
        except:
            pass


# Singleton instance for global access
_db_instance = None

def get_database() -> DatabaseManager:
    """Get or create singleton database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
