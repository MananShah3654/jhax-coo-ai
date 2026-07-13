"""
CRUD / onboarding routes for JhaPay AI COO.

These let a signed-in owner build their real data — restaurants (locations),
menu items, customers, and orders — instead of relying on a mock seed. Every
route is authenticated with `get_current_user`, stamps `owner_id = user.id`
server-side, and validates that any referenced restaurant/customer/menu id
belongs to the caller. This is the tenant-isolation boundary for writes; the
read/analytics side is isolated by PostgresDataSource(owner_id).

Mounted under /api by server.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import (
    Customer, MenuItem, Order, OrderItem, Restaurant, User, get_db,
)

crud = APIRouter(prefix="/api")


# ==================== helpers ====================
def _own_restaurant(db: Session, user: User, restaurant_id: str) -> Restaurant:
    """Fetch a restaurant, 404 if it doesn't exist or isn't the caller's."""
    r = db.get(Restaurant, restaurant_id)
    if r is None or r.owner_id != user.id:
        raise HTTPException(404, "Restaurant not found")
    return r


def _own_menu_item(db: Session, user: User, item_id: str) -> MenuItem:
    m = db.get(MenuItem, item_id)
    if m is None or m.owner_id != user.id:
        raise HTTPException(404, "Menu item not found")
    return m


def _own_customer(db: Session, user: User, customer_id: str) -> Customer:
    c = db.get(Customer, customer_id)
    if c is None or c.owner_id != user.id:
        raise HTTPException(404, "Customer not found")
    return c


# ==================== restaurants ====================
class RestaurantIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    city: str | None = None
    address: str | None = None
    manager: str | None = None
    phone: str | None = None


class RestaurantPatch(BaseModel):
    name: str | None = None
    city: str | None = None
    address: str | None = None
    manager: str | None = None
    phone: str | None = None
    is_active: bool | None = None


@crud.post("/restaurants")
def create_restaurant(
    req: RestaurantIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = Restaurant(owner_id=user.id, **req.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r.to_dict()


@crud.get("/restaurants")
def list_restaurants(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = (db.query(Restaurant)
            .filter_by(owner_id=user.id)
            .order_by(Restaurant.created_at).all())
    return {"restaurants": [r.to_dict() for r in rows]}


@crud.patch("/restaurants/{restaurant_id}")
def update_restaurant(
    restaurant_id: str,
    req: RestaurantPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = _own_restaurant(db, user, restaurant_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return r.to_dict()


@crud.delete("/restaurants/{restaurant_id}")
def delete_restaurant(
    restaurant_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Soft delete so historical orders/analytics stay intact.
    r = _own_restaurant(db, user, restaurant_id)
    r.is_active = False
    db.commit()
    return {"ok": True, "id": restaurant_id, "is_active": False}


# ==================== menu ====================
class MenuItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = "Uncategorized"
    price: float = Field(ge=0)
    cost: float = Field(ge=0)
    featured: bool = False


class MenuItemPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    price: float | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)
    featured: bool | None = None
    is_active: bool | None = None


@crud.post("/restaurants/{restaurant_id}/menu")
def create_menu_item(
    restaurant_id: str,
    req: MenuItemIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _own_restaurant(db, user, restaurant_id)
    m = MenuItem(owner_id=user.id, restaurant_id=restaurant_id, **req.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m.to_dict()


@crud.get("/menu/items")
def list_menu_items(
    restaurant_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(MenuItem).filter_by(owner_id=user.id)
    if restaurant_id:
        _own_restaurant(db, user, restaurant_id)
        q = q.filter_by(restaurant_id=restaurant_id)
    return {"items": [m.to_dict() for m in q.order_by(MenuItem.name).all()]}


@crud.patch("/menu/items/{item_id}")
def update_menu_item(
    item_id: str,
    req: MenuItemPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = _own_menu_item(db, user, item_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return m.to_dict()


@crud.delete("/menu/items/{item_id}")
def delete_menu_item(
    item_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = _own_menu_item(db, user, item_id)
    m.is_active = False
    db.commit()
    return {"ok": True, "id": item_id, "is_active": False}


# ==================== customers ====================
class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None
    restaurant_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class CustomerPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    restaurant_id: str | None = None
    tags: list[str] | None = None
    loyalty_points: int | None = None


@crud.post("/customers")
def create_customer(
    req: CustomerIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.restaurant_id:
        _own_restaurant(db, user, req.restaurant_id)
    c = Customer(owner_id=user.id, **req.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.to_dict()


@crud.get("/customers/list")
def list_customers(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = (db.query(Customer)
            .filter_by(owner_id=user.id)
            .order_by(Customer.name).all())
    return {"customers": [c.to_dict() for c in rows]}


@crud.patch("/customers/{customer_id}")
def update_customer(
    customer_id: str,
    req: CustomerPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = _own_customer(db, user, customer_id)
    data = req.model_dump(exclude_unset=True)
    if data.get("restaurant_id"):
        _own_restaurant(db, user, data["restaurant_id"])
    for field, value in data.items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c.to_dict()


# ==================== orders (analytics-critical write path) ====================
class OrderLineIn(BaseModel):
    menu_item_id: str
    qty: int = Field(ge=1)


class OrderIn(BaseModel):
    restaurant_id: str
    customer_id: str | None = None
    channel: str = "Dine In"
    placed_at: datetime | None = None
    tax: float = Field(default=0.0, ge=0)
    tip: float = Field(default=0.0, ge=0)
    wait_minutes: int = Field(default=0, ge=0)
    rating: int = Field(default=5, ge=1, le=5)
    items: list[OrderLineIn] = Field(min_length=1)


@crud.post("/orders")
def create_order(
    req: OrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an order with line items.

    price/cost/name are SNAPSHOTTED from each menu item at sale time so later
    menu edits don't rewrite historical KPIs. subtotal = Σ qty*price;
    total = subtotal + tax + tip.
    """
    _own_restaurant(db, user, req.restaurant_id)
    if req.customer_id:
        _own_customer(db, user, req.customer_id)

    placed_at = req.placed_at or datetime.now(timezone.utc)
    if placed_at.tzinfo is None:
        placed_at = placed_at.replace(tzinfo=timezone.utc)

    line_items: list[OrderItem] = []
    subtotal = 0.0
    for line in req.items:
        m = _own_menu_item(db, user, line.menu_item_id)
        if m.restaurant_id != req.restaurant_id:
            raise HTTPException(
                400, f"Menu item {m.id} does not belong to this restaurant"
            )
        subtotal += line.qty * m.price
        line_items.append(OrderItem(
            menu_item_id=m.id, name=m.name, qty=line.qty,
            price=m.price, cost=m.cost,
        ))

    subtotal = round(subtotal, 2)
    total = round(subtotal + req.tax + req.tip, 2)
    order = Order(
        owner_id=user.id, restaurant_id=req.restaurant_id,
        customer_id=req.customer_id, placed_at=placed_at, channel=req.channel,
        subtotal=subtotal, tax=req.tax, tip=req.tip, total=total,
        wait_minutes=req.wait_minutes, rating=req.rating, items=line_items,
    )
    db.add(order)

    # Best-effort loyalty bump so customer analytics reflects the visit.
    if req.customer_id:
        c = db.get(Customer, req.customer_id)
        c.visits = (c.visits or 0) + 1
        c.last_visit_at = placed_at
        c.lifetime_value = round((c.lifetime_value or 0.0) + total, 2)
        c.avg_spend = round(c.lifetime_value / max(c.visits, 1), 2)

    db.commit()
    db.refresh(order)
    return order.to_dict()


@crud.get("/orders")
def list_orders(
    restaurant_id: str | None = None,
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = (db.query(Order)
         .filter(Order.owner_id == user.id, Order.placed_at >= cutoff))
    if restaurant_id:
        _own_restaurant(db, user, restaurant_id)
        q = q.filter(Order.restaurant_id == restaurant_id)
    rows = q.order_by(Order.placed_at.desc()).all()
    return {"days": days, "orders": [o.to_dict() for o in rows]}
