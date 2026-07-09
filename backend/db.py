"""
PostgreSQL persistence layer for JhaPay AI COO.

SQLAlchemy 2.0 models that mirror the exact data shapes the app already
uses (see mock_data.py). Nested/variable fields (`order.items`,
`customer.tags`) are stored as JSONB so the DataSource can hand analytics.py
the identical dicts it got from the mock dataset — no analytics changes needed.

Single-restaurant for now (no tenant columns yet — that comes later).
"""
from __future__ import annotations

import os
from typing import Dict, List

from sqlalchemy import Float, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/jhapay_coo"
)

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


class Owner(Base):
    __tablename__ = "owner"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    restaurant: Mapped[str] = mapped_column(String)

    def to_dict(self) -> Dict:
        return {"name": self.name, "restaurant": self.restaurant}


class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    manager: Mapped[str] = mapped_column(String)

    def to_dict(self) -> Dict:
        return {"id": self.id, "name": self.name, "city": self.city, "manager": self.manager}


class MenuItem(Base):
    __tablename__ = "menu_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float)

    def to_dict(self) -> Dict:
        return {"id": self.id, "name": self.name, "category": self.category,
                "price": self.price, "cost": self.cost}


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    visits: Mapped[int] = mapped_column(Integer)
    last_visit_days_ago: Mapped[int] = mapped_column(Integer)
    avg_spend: Mapped[float] = mapped_column(Float)
    lifetime_value: Mapped[float] = mapped_column(Float)
    loyalty_points: Mapped[int] = mapped_column(Integer)
    favorite_branch: Mapped[str] = mapped_column(String)
    tags: Mapped[list] = mapped_column(JSONB)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name, "phone": self.phone, "email": self.email,
            "visits": self.visits, "last_visit_days_ago": self.last_visit_days_ago,
            "avg_spend": self.avg_spend, "lifetime_value": self.lifetime_value,
            "loyalty_points": self.loyalty_points, "favorite_branch": self.favorite_branch,
            "tags": self.tags,
        }


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    branch_id: Mapped[str] = mapped_column(String, index=True)
    ts: Mapped[str] = mapped_column(Text, index=True)  # ISO string, kept verbatim
    channel: Mapped[str] = mapped_column(String)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    items: Mapped[list] = mapped_column(JSONB)
    subtotal: Mapped[float] = mapped_column(Float)
    tax: Mapped[float] = mapped_column(Float)
    tip: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    wait_minutes: Mapped[int] = mapped_column(Integer)
    rating: Mapped[int] = mapped_column(Integer)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "branch_id": self.branch_id, "ts": self.ts,
            "channel": self.channel, "customer_id": self.customer_id, "items": self.items,
            "subtotal": self.subtotal, "tax": self.tax, "tip": self.tip, "total": self.total,
            "wait_minutes": self.wait_minutes, "rating": self.rating,
        }


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
