import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Where our Postgres database lives. Falls back to a local default for dev.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/watchpost"
)

engine = create_engine(DATABASE_URL)

# SessionLocal is a factory that gives us a fresh "conversation" with the DB per request
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent class every table model inherits from
Base = declarative_base()

def get_db():
    """Gives each API request its own DB session, and always closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()