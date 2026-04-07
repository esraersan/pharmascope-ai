"""Database connection and session management."""

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = (
        "postgresql://pharmascope:pharmascope@localhost:5432/pharmascope"
    )

    class Config:
        env_file = ".env"


settings = Settings()


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Yield a database session and close it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    """Test that the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("database_connection_ok")
        return True
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        return False
