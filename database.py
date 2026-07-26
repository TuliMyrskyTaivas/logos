from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
import os

# SQLAlchemy Database URL configuration
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "financial_db")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_session(user: str, passwordEnv: str) -> sessionmaker[Session]:
    """
    Create and return a SQLAlchemy session factory for the given database user.
    """
    password = os.getenv(passwordEnv)
    if password is None: raise ValueError(f"Environment variable {passwordEnv} is not set")

    url = f"postgresql://{user}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(url, echo=False)
    return sessionmaker(bind=engine)