"""
Unit tests for SQLite database lifecycle and schema initialization.
"""

import sqlite3
import tempfile
from pathlib import Path
from app import create_app
from app.config import Config
from app.database import init_db, get_db


def test_database_initialization():
    """Verify that init_db creates all required tables and default records."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_disaster.db"

        class TempConfig(Config):
            TESTING = True
            DATABASE_PATH = test_db_path

        app = create_app(TempConfig)

        with app.app_context():
            init_db()

            db = get_db()
            cursor = db.cursor()

            # Verify that all 4 tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}

            expected_tables = {"hazards", "incidents", "source_sync_status", "audit_logs"}
            for t in expected_tables:
                assert t in tables, f"Expected table '{t}' was not found in database."

            # Verify source_sync_status default records were seeded
            cursor.execute("SELECT COUNT(*) FROM source_sync_status;")
            sources_count = cursor.fetchone()[0]
            assert sources_count == 4, f"Expected 4 initial data sources, got {sources_count}"


def test_hazard_insertion_and_query():
    """Verify inserting and querying a hazard record in SQLite."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_disaster.db"

        class TempConfig(Config):
            TESTING = True
            DATABASE_PATH = test_db_path

        app = create_app(TempConfig)

        with app.app_context():
            init_db()
            db = get_db()

            db.execute(
                """
                INSERT INTO hazards (source, hazard_type, latitude, longitude, intensity_value, confidence, observation_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("NASA_FIRMS", "FIRE", 28.5383, 77.3820, 45.2, 0.95, "2026-10-31T12:00:00Z")
            )
            db.commit()

            cursor = db.execute("SELECT * FROM hazards WHERE hazard_type = 'FIRE';")
            row = cursor.fetchone()
            assert row is not None
            assert row["source"] == "NASA_FIRMS"
            assert row["latitude"] == 28.5383
            assert row["confidence"] == 0.95

