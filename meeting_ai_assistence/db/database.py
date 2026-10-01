from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Initialize database tables and apply lightweight migrations."""
    Base.metadata.create_all(bind=engine)
    
    # Safe migration for existing SQLite databases
    if "sqlite" in settings.DATABASE_URL:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("PRAGMA table_info(questions);")).fetchall()
                existing_cols = [row[1] for row in res]
                if "reasoning" not in existing_cols:
                    conn.execute(text("ALTER TABLE questions ADD COLUMN reasoning TEXT;"))
                if "user_say" not in existing_cols:
                    conn.execute(text("ALTER TABLE questions ADD COLUMN user_say TEXT;"))
                conn.commit()
        except Exception:
            pass
