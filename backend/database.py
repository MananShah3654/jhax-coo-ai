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
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker,
)


def _uuid() -> str:
    """App-generated string primary key (UUID4 hex, 32 chars)."""
    return uuid.uuid4().hex

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


# -------------------- Business / tenant data --------------------
# The Firebase `User` above IS the owner (tenant root). Every business row
# carries a denormalized `owner_id` FK for fast, simple tenant filtering.
# A "restaurant" is a physical location (the old single-tenant `Branch`).
#
# to_dict() on each model emits the EXACT legacy dict shape analytics.py
# consumes (see analytics.py) so the analytics engine needs no changes:
#   order  -> {ts, branch_id, total, subtotal, tip, tax, customer_id,
#              channel, rating, wait_minutes, items:[{menu_id,qty,price,cost,name}]}
#   branch -> {id, name, city, manager, ...}
#   menu   -> {id, name, category, price, cost}
#   customer -> {tags, visits, lifetime_value, ...}
class Restaurant(Base):
    """A physical location owned by a User. Replaces the old `Branch`."""
    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manager: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def to_dict(self) -> dict:
        # Analytics needs id + name; city/manager pass through for the UI.
        return {
            "id": self.id, "name": self.name, "city": self.city,
            "manager": self.manager, "address": self.address, "phone": self.phone,
        }


class MenuItem(Base):
    """A sellable item on one restaurant's menu (restaurant-scoped)."""
    __tablename__ = "menu_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(120), default="Uncategorized")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def to_dict(self) -> dict:
        # price/cost pass through; analytics reads them off order items, not here.
        return {
            "id": self.id, "name": self.name, "category": self.category,
            "price": self.price, "cost": self.cost, "featured": self.featured,
        }


class Customer(Base):
    """A loyalty customer of an owner (owner-scoped; shared across locations)."""
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Optional "home" location; loyalty/LTV are analyzed owner-wide.
    restaurant_id: Mapped[str | None] = mapped_column(
        ForeignKey("restaurants.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    visits: Mapped[int] = mapped_column(Integer, default=0)
    last_visit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avg_spend: Mapped[float] = mapped_column(Float, default=0.0)
    lifetime_value: Mapped[float] = mapped_column(Float, default=0.0)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def to_dict(self) -> dict:
        days = None
        if self.last_visit_at:
            last = self.last_visit_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days = (datetime.now(timezone.utc) - last).days
        return {
            "id": self.id, "name": self.name, "phone": self.phone,
            "email": self.email, "visits": self.visits,
            "last_visit_days_ago": days, "avg_spend": self.avg_spend,
            "lifetime_value": self.lifetime_value,
            "loyalty_points": self.loyalty_points, "tags": self.tags or [],
        }


class Order(Base):
    """A single order at one restaurant. Money fields are snapshots at sale time."""
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str] = mapped_column(String(40), default="Dine In")
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)
    tip: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    wait_minutes: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    # selectin so a batch of orders loads its line items in one extra query (no N+1).
    items: Mapped[list["OrderItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        placed = self.placed_at
        if placed.tzinfo is None:
            placed = placed.replace(tzinfo=timezone.utc)
        return {
            "id": self.id, "branch_id": self.restaurant_id,
            "ts": placed.isoformat(), "channel": self.channel,
            "customer_id": self.customer_id or "",
            "items": [i.to_dict() for i in self.items],
            "subtotal": self.subtotal, "tax": self.tax, "tip": self.tip,
            "total": self.total, "wait_minutes": self.wait_minutes,
            "rating": self.rating,
        }


class OrderItem(Base):
    """One line item of an order. name/price/cost are snapshots at sale time."""
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    menu_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)

    def to_dict(self) -> dict:
        # Analytics joins on menu_id and reads qty/price/cost from here.
        return {
            "menu_id": self.menu_item_id, "qty": self.qty,
            "price": self.price, "cost": self.cost, "name": self.name,
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
