import logging
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set.")
    raise RuntimeError("DATABASE_URL environment variable must be set")

# Optional: Enable SQLAlchemy echo from env var, default to False
SQL_ECHO = os.getenv("SQL_ECHO", "False").lower() in ("true", "1", "yes")

logger.info(f"Setting up database using URL: {DATABASE_URL}")

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Yield a new database session, committing if no exceptions occur,
    rolling back otherwise, and always closing the session.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()