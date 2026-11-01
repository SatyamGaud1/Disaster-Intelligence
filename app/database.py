"""
Database management module for SQLite.
Handles connection pooling per request, schema initialization, and database lifecycle.
"""

import sqlite3
from pathlib import Path
from flask import g, current_app
from app.models.schema import SCHEMA_SQL


def get_db(db_path: Path = None) -> sqlite3.Connection:
    """
    Returns an active SQLite database connection for the current application context.
    If already connected in this request, reuses g.db.
    """
    if "db" not in g:
        target_path = db_path or current_app.config["DATABASE_PATH"]
        
        # Ensure parent directory exists
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Create connection with row factory for dictionary-like column access
        g.db = sqlite3.connect(
            target_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        g.db.row_factory = sqlite3.Row
        
        # Enable foreign keys and Write-Ahead Logging for improved concurrency
        g.db.execute("PRAGMA foreign_keys = ON;")
        g.db.execute("PRAGMA journal_mode = WAL;")

    return g.db


def close_db(e=None) -> None:
    """Closes the database connection at the end of the request lifecycle."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app=None) -> None:
    """
    Initializes the database schema using SCHEMA_SQL.
    Can be run within an active app context or given an app instance.
    """
    def _run_init():
        db = get_db()
        db.executescript(SCHEMA_SQL)
        
        # Initialize default satellite source tracking rows if not present
        default_sources = [
            ("NASA_FIRMS", "Active Fire & Thermal Anomalies", "READY"),
            ("SENTINEL_1", "SAR Inundation & Flood Mapping", "READY"),
            ("SENTINEL_2", "Optical Multispectral & Drought Indices", "READY"),
            ("NASA_GPM", "Global Precipitation Measurement", "READY"),
        ]
        
        for source_name, desc, status in default_sources:
            db.execute(
                """
                INSERT OR IGNORE INTO source_sync_status (source_name, status, records_count, message)
                VALUES (?, ?, 0, ?)
                """,
                (source_name, status, f"Initialized data source: {desc}")
            )
        
        db.commit()

        # Seed default verified helping organizations and responder accounts
        from app.services.response_service import seed_default_organizations
        seed_default_organizations()

        # Seed default verified shelters, emergency facilities, and road hazards
        from app.services.evacuation_service import seed_default_evacuation_data
        seed_default_evacuation_data()

    if app:
        with app.app_context():
            _run_init()
    else:
        _run_init()

