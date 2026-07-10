"""
Local PostgreSQL persistence for JhaPay AI COO.

Uses SQLAlchemy 2.0 (sync engine + psycopg2). The connection string comes from
DATABASE_URL in .env, e.g.:

    DATABASE_URL=postgresql://postgres:postgres@localhost:5433/jhax_coo

Call `init_db()` once on startup to create tables. Use `get_db()` as a FastAPI
dependency to get a session that is always closed after the request.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import DateTime, String, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/jhax_coo"
)

# pool_pre_ping avoids stale-connection errors after Postgres restarts / idle.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    restaurant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # bcrypt hash of the user's quick-unlock PIN (never returned to the client).
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "firebase_uid": self.firebase_uid,
            "email": self.email,
            "phone_number": self.phone_number,
            "name": self.name,
            "restaurant_name": self.restaurant_name,
            # Expose only whether a PIN exists, never the hash itself.
            "has_pin": bool(self.pin_hash),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db() -> None:
    """Create all tables if they don't exist (idempotent).

    We use create_all() instead of migrations while the schema is young. Since
    create_all() won't ALTER existing tables, add any newly-introduced columns
    here idempotently so older databases pick them up on the next boot.
    """
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(255)")
        )


# -------------------- PIN quick-unlock helpers --------------------
def set_user_pin(db, user: User, pin: str) -> User:
    """Hash and store a user's PIN (bcrypt)."""
    user.pin_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db.commit()
    db.refresh(user)
    return user


def verify_user_pin(user: User, pin: str) -> bool:
    """Check a PIN against the stored hash. False if the user has no PIN."""
    if not user.pin_hash:
        return False
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), user.pin_hash.encode("utf-8"))
    except ValueError:
        return False


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_user(db, *, firebase_uid: str, **fields) -> User:
    """Look up a user by Firebase UID, creating (or refreshing) it as needed.

    `fields` may include email, phone_number, name, restaurant_name. On an
    existing row, any non-null incoming value overwrites the stored one so the
    local record tracks the latest Firebase profile.
    """
    user = db.query(User).filter(User.firebase_uid == firebase_uid).one_or_none()
    if user is None:
        user = User(firebase_uid=firebase_uid, **fields)
        db.add(user)
    else:
        for key, value in fields.items():
            if value is not None:
                setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
