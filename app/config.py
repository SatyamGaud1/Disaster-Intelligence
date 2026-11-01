import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory: root folder of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-disaster-intelligence-platform")
    DEBUG = False
    TESTING = False
    
    # Database configuration
    DB_FILENAME = os.getenv("DATABASE_PATH", "data/disaster_intel.db")
    DATABASE_PATH = BASE_DIR / DB_FILENAME if not os.path.isabs(DB_FILENAME) else Path(DB_FILENAME)
    
    # External Data Source Configuration (Public & Free)
    NASA_FIRMS_MAP_KEY = os.getenv("NASA_FIRMS_MAP_KEY", "")


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    # In-memory database or dedicated test db for tests
    DATABASE_PATH = BASE_DIR / "data" / "test_disaster_intel.db"


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

