"""Database configuration and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DATA_DIR

# Database path
DATABASE_URL = f"sqlite:///{DATA_DIR / 'flashcards.db'}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Run database migrations for schema updates."""
    with engine.connect() as conn:
        # Check if sessions table exists first
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"))
        if result.fetchone():
            # Check if source_type column exists in sessions table
            result = conn.execute(text("PRAGMA table_info(sessions)"))
            columns = [row[1] for row in result.fetchall()]

            if "source_type" not in columns:
                print("Adding source_type column to sessions table...")
                conn.execute(text("ALTER TABLE sessions ADD COLUMN source_type VARCHAR(50) DEFAULT 'pdf'"))
                conn.commit()
                print("Migration complete: source_type column added")

        # Check if card_images table exists
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='card_images'"))
        if not result.fetchone():
            print("Creating card_images table...")
            conn.execute(text("""
                CREATE TABLE card_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER NOT NULL,
                    session_id INTEGER NOT NULL,
                    original_filename VARCHAR(500) NOT NULL,
                    stored_filename VARCHAR(500) NOT NULL,
                    media_type VARCHAR(100) DEFAULT 'image/png',
                    file_size INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """))
            conn.commit()
            print("Migration complete: card_images table created")


def init_db() -> None:
    """Initialize the database by creating all tables."""
    from backend.db.models import Base
    Base.metadata.create_all(bind=engine)

    # Run migrations for existing databases
    run_migrations()
