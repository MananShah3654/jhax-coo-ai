"""
JhaPay AI COO - Analytics helpers.

Pure functions that read the in-memory DATASET and compute KPIs, branch
performance, customer cohorts, menu performance, forecasts, and a
restaurant Health Score. These power both the /api/* business endpoints
and the structured `restaurant_context` injected into the AI prompt.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from data_source import get_source

DS = get_source()

# Business hours 07:00–22:00 = 15 hours/day. Matches the 7–22 windows used by
# revenue_breakdown()/forecast(). Denominator for RevPASH (seats × hours × days).
SERVICE_HOURS_PER_DAY = 15

# Channel buckets. Cart abandonment applies to online channels only (a walk-in
# has no checkout to abandon). Seating KPIs (turnover, RevPASH) count *seated*
# orders = everything that isn't explicitly online — this works regardless of how
# a POS labels in-house dining (Square uses source names like "Point of Sale",
# not the literal "Dine In", so matching a dine-in whitelist would miss them all).
_ONLINE_CHANNELS = {"to-go", "to go", "togo", "delivery"}


def _channel(o: Dict) -> str:
    return (o.get("channel") or "").strip().lower()


def _is_seated(o: Dict) -> bool:
    """A seated (in-house) order — anything not routed through an online channel."""
    return _channel(o) not in _ONLINE_CHANNELS


# Read branches/menu fresh on every call (not frozen at import) so a live
# data source with a cache TTL actually surfaces refreshed catalog data.
def _branches():
    return DS.branches()


def _menu():
    return DS.menu()


def _customers():
    return DS.customers()


def _orders():
    return DS.orders()


def _owner():
    return DS.owner()


def _carts():
    """Abandoned checkout sessions, or [] if the source doesn't expose them."""
    fn = getattr(DS, "carts", None)
    return fn() if callable(fn) else []


def _carts_supported() -> bool:
    """True when the active data source can report abandoned-cart sessions.

    Mock supports it; a POS adapter (Square/JhaPOS) does not, so the Cart
    Abandonment KPI is reported as None (unavailable) rather than a fake 0%.
    """
    return callable(getattr(DS, "carts", None))


def _capacity(branch_id: str | None = None) -> Dict[str, int]:
    """Seats + tables for a branch, or summed across all branches when None.

    Returns zeros when the source carries no capacity data (e.g. Square), which
    makes the seating KPIs (turnover, RevPASH) degrade to None instead of
    dividing by zero."""
    seats = tables = 0
    for b in _branches():
        if branch_id is None or b.get("id") == branch_id:
            seats += b.get("seats") or 0
            tables += b.get("tables") or 0
    return {"seats": seats, "tables": tables}


def carts_between(start: datetime, end: datetime, branch_id: str | None = None) -> List[Dict]:
    out = []
    for c in _carts():
        ts = _parse(c["ts"])
        if start <= ts < end and (branch_id is None or c.get("branch_id") == branch_id):
            out.append(c)
    return out


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _today() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def orders_between(start: datetime, end: datetime, branch_id: str | None = None) -> List[Dict]:
    out = []
    for o in _orders():
        ts = _parse(o["ts"])
        if start <= ts < end and (branch_id is None or o["branch_id"] == branch_id):
            out.append(o)
    return out


def kpi_window(start: datetime, end: datetime, branch_id: str | None = None) -> Dict:
    orders = orders_between(start, end, branch_id)
    revenue = sum(o["total"] for o in orders)
    subtotal = sum(o["subtotal"] for o in orders)
    tips = sum(o["tip"] for o in orders)
    count = len(orders)
    unique_customers = len({o["customer_id"] for o in orders})
    aov = revenue / count if count else 0.0
    cost = sum(i["cost"] * i["qty"] for o in orders for i in o["items"])

    # --- Covers: total guests served (party sizes; ≥1 per order) ---
    covers = sum(o.get("party_size") or 1 for o in orders)

    # --- Average discount %: total discount as a share of subtotal ---
    discount_total = sum(o.get("discount", 0.0) for o in orders)
    avg_discount_pct = (discount_total / subtotal * 100) if subtotal else 0.0

    # --- Seating KPIs (dine-in only) — need physical capacity ---
    num_days = (end - start).total_seconds() / 86400.0
    cap = _capacity(branch_id)
    seated = [o for o in orders if _is_seated(o)]
    seated_revenue = sum(o["total"] for o in seated)
    # Table Turnover: seated parties per table per day. One seated order ≈ one
    # table turn. None when capacity/duration is unknown (never a fake 0).
    table_turnover = (
        round(len(seated) / cap["tables"] / num_days, 2)
        if cap["tables"] and num_days > 0 else None
    )
    # RevPASH: seated (in-house) revenue per available seat-hour.
    seat_hours = cap["seats"] * SERVICE_HOURS_PER_DAY * num_days
    revpash = round(seated_revenue / seat_hours, 2) if seat_hours > 0 else None

    # --- Cart Abandonment Rate: abandoned / (abandoned + completed-online) ---
    # Only meaningful for online channels; None when the source has no cart stream.
    if _carts_supported():
        abandoned = len(carts_between(start, end, branch_id))
        online_completed = sum(1 for o in orders if _channel(o) in _ONLINE_CHANNELS)
        denom = abandoned + online_completed
        cart_abandonment_pct = round(abandoned / denom * 100, 1) if denom else 0.0
    else:
        cart_abandonment_pct = None

    return {
        "revenue":            round(revenue, 2),
        "subtotal":           round(subtotal, 2),
        "orders":             count,
        "covers":             covers,
        "customers":          unique_customers,
        "avg_order_value":    round(aov, 2),
        "avg_discount_pct":   round(avg_discount_pct, 1),
        "table_turnover":     table_turnover,
        "revpash":            revpash,
        "cart_abandonment_pct": cart_abandonment_pct,
        "tips":               round(tips, 2),
        "gross_margin":       round((subtotal - cost) / subtotal * 100, 1) if subtotal else 0.0,
    }


def today_kpis(branch_id: str | None = None) -> Dict:
    today = _today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    last_week_today = today - timedelta(days=7)
    last_week_tom = last_week_today + timedelta(days=1)

    today_k = kpi_window(today, tomorrow, branch_id)
    yest_k = kpi_window(yesterday, today, branch_id)
    lw_k = kpi_window(last_week_today, last_week_tom, branch_id)

    def _pct(a: float, b: float) -> float:
        if not b:
            return 0.0
        return round((a - b) / b * 100, 1)

    return {
        **today_k,
        # Revenue deltas.
        "vs_yesterday_pct": _pct(today_k["revenue"], yest_k["revenue"]),
        "vs_last_week_pct": _pct(today_k["revenue"], lw_k["revenue"]),
        # Order-count + AOV deltas — let the AI decompose a revenue move into its
        # drivers (revenue = orders x average order value).
        "orders_vs_yesterday_pct": _pct(today_k["orders"], yest_k["orders"]),
        "orders_vs_last_week_pct": _pct(today_k["orders"], lw_k["orders"]),
        "aov_vs_yesterday_pct": _pct(today_k["avg_order_value"], yest_k["avg_order_value"]),
        "aov_vs_last_week_pct": _pct(today_k["avg_order_value"], lw_k["avg_order_value"]),
        # Covers (guests) deltas — the other half of the traffic story.
        "covers_vs_yesterday_pct": _pct(today_k["covers"], yest_k["covers"]),
        "covers_vs_last_week_pct": _pct(today_k["covers"], lw_k["covers"]),
    }


def branch_performance(days: int = 7) -> List[Dict]:
    end = _today() + timedelta(days=1)
    start = end - timedelta(days=days)
    prev_end = start
    prev_start = prev_end - timedelta(days=days)
    out = []
    for b in _branches():
        cur = kpi_window(start, end, b["id"])
        prev = kpi_window(prev_start, prev_end, b["id"])
        growth = 0.0 if not prev["revenue"] else round((cur["revenue"] - prev["revenue"]) / prev["revenue"] * 100, 1)
        out.append({**b, **cur, "growth_pct": growth})
    out.sort(key=lambda x: x["revenue"], reverse=True)
    return out


def menu_performance(days: int = 30) -> List[Dict]:
    end = _today() + timedelta(days=1)
    start = end - timedelta(days=days)
    agg = defaultdict(lambda: {"qty": 0, "revenue": 0.0, "cost": 0.0})
    for o in orders_between(start, end):
        for it in o["items"]:
            a = agg[it["menu_id"]]
            a["qty"] += it["qty"]
            a["revenue"] += it["qty"] * it["price"]
            a["cost"] += it["qty"] * it["cost"]
    out = []
    for m in _menu():
        a = agg[m["id"]]
        profit = a["revenue"] - a["cost"]
        margin = (profit / a["revenue"] * 100) if a["revenue"] else 0.0
        out.append({**m, "units_sold": a["qty"], "revenue": round(a["revenue"], 2),
                    "profit": round(profit, 2), "margin_pct": round(margin, 1)})
    out.sort(key=lambda x: x["revenue"], reverse=True)
    return out


def customer_intelligence() -> Dict:
    customers = _customers()
    vip = [c for c in customers if "vip" in c["tags"]]
    at_risk = [c for c in customers if "at_risk" in c["tags"]]
    new = [c for c in customers if "new" in c["tags"]]
    repeat = [c for c in customers if c["visits"] >= 2]
    avg_ltv = sum(c["lifetime_value"] for c in customers) / max(len(customers), 1)
    return {
        "total_customers": len(customers),
        "vip_count": len(vip),
        "at_risk_count": len(at_risk),
        "new_count": len(new),
        "repeat_rate_pct": round(len(repeat) / max(len(customers), 1) * 100, 1),
        "avg_lifetime_value": round(avg_ltv, 2),
        "top_vips": sorted(vip, key=lambda c: c["lifetime_value"], reverse=True)[:8],
        "at_risk_list": sorted(at_risk, key=lambda c: c["lifetime_value"], reverse=True)[:8],
    }


def revenue_breakdown(days: int = 30) -> Dict:
    end = _today() + timedelta(days=1)
    start = end - timedelta(days=days)
    by_channel = defaultdict(float)
    by_day = defaultdict(float)
    by_hour = defaultdict(float)
    for o in orders_between(start, end):
        by_channel[o["channel"]] += o["total"]
        d = _parse(o["ts"]).date().isoformat()
        by_day[d] += o["total"]
        by_hour[_parse(o["ts"]).hour] += o["total"]
    return {
        "by_channel": [{"channel": k, "revenue": round(v, 2)} for k, v in by_channel.items()],
        "by_day":     [{"date": k, "revenue": round(v, 2)} for k, v in sorted(by_day.items())],
        "by_hour":    [{"hour": h, "revenue": round(by_hour.get(h, 0.0), 2)} for h in range(7, 23)],
    }


def forecast(days_ahead: int = 30) -> Dict:
    # Simple naive forecast: last 14d daily avg with weekend uplift
    end = _today()
    start = end - timedelta(days=14)
    by_day = defaultdict(float)
    for o in orders_between(start, end):
        by_day[_parse(o["ts"]).date().isoformat()] += o["total"]
    daily = list(by_day.values()) or [0.0]
    avg = sum(daily) / len(daily)
    proj = []
    total = 0.0
    for i in range(days_ahead):
        d = end + timedelta(days=i + 1)
        mult = 1.18 if d.weekday() >= 5 else 1.0
        val = round(avg * mult, 2)
        proj.append({"date": d.date().isoformat(), "projected_revenue": val})
        total += val
    return {
        "horizon_days": days_ahead,
        "projected_revenue": round(total, 2),
        "daily_avg": round(avg, 2),
        "confidence": 78,
        "series": proj,
    }


def health_score() -> Dict:
    """0–100 score with component breakdown — feeds the Apple-watch ring."""
    # Revenue growth (7d vs prior 7d)
    end = _today() + timedelta(days=1)
    cur = kpi_window(end - timedelta(days=7), end)
    prev = kpi_window(end - timedelta(days=14), end - timedelta(days=7))
    growth = 0.0 if not prev["revenue"] else (cur["revenue"] - prev["revenue"]) / prev["revenue"] * 100

    ci = customer_intelligence()
    repeat = ci["repeat_rate_pct"]

    # Avg rating last 30d
    end30 = _today() + timedelta(days=1)
    last30 = orders_between(end30 - timedelta(days=30), end30)
    avg_rating = sum(o["rating"] for o in last30) / max(len(last30), 1)
    avg_wait = sum(o["wait_minutes"] for o in last30) / max(len(last30), 1)

    # Tip percentage (proxy for staff service quality)
    tip_pct = (sum(o["tip"] for o in last30) / sum(o["subtotal"] for o in last30) * 100) if last30 else 0.0

    components = {
        "revenue_growth": max(0, min(100, 50 + growth * 4)),     # +12% -> 98
        "repeat_customers": max(0, min(100, repeat * 1.5)),
        "reviews": max(0, min(100, (avg_rating - 3) * 50 + 50)),  # 4.5 -> 75
        "wait_times": max(0, min(100, 100 - max(0, avg_wait - 8) * 6)),
        "tips": max(0, min(100, tip_pct * 5)),                   # 18% -> 90
        "staff_efficiency": max(0, min(100, 100 - max(0, avg_wait - 10) * 5)),
    }
    score = round(sum(components.values()) / len(components))
    state = "green" if score >= 75 else "yellow" if score >= 55 else "red"
    return {
        "score": score,
        "state": state,
        "components": {k: round(v) for k, v in components.items()},
    }


def daily_briefing() -> Dict:
    today = _today()
    yesterday_k = kpi_window(today - timedelta(days=1), today)
    day_before_k = kpi_window(today - timedelta(days=2), today - timedelta(days=1))
    growth = 0.0
    if day_before_k["revenue"]:
        growth = round((yesterday_k["revenue"] - day_before_k["revenue"]) / day_before_k["revenue"] * 100, 1)
    menu = menu_performance(7)
    branches = branch_performance(7)
    ci = customer_intelligence()
    worst_branch = branches[-1]
    best_branch = branches[0]
    top_seller = menu[0]
    worst_seller = menu[-1]
    opportunity = round(ci["at_risk_count"] * ci["avg_lifetime_value"] * 0.15, 0)
    return {
        "owner_name": _owner()["name"],
        "yesterday_revenue": yesterday_k["revenue"],
        "yesterday_orders": yesterday_k["orders"],
        "growth_pct": growth,
        "top_seller": top_seller["name"],
        "worst_performer": worst_seller["name"],
        "best_branch": best_branch["name"],
        "worst_branch": worst_branch["name"],
        "risk_areas": [
            f"{ci['at_risk_count']} customers haven't returned in 30+ days",
            f"{worst_branch['name']} branch is {abs(worst_branch['growth_pct'])}% {'down' if worst_branch['growth_pct'] < 0 else 'up'} week-over-week",
        ],
        "recommended_action": (
            "Launch a reactivation campaign to inactive customers and run a "
            "lunch combo promo at the Downtown branch this week."
        ),
        "expected_opportunity": opportunity,
    }


def operations_snapshot() -> Dict:
    end = _today() + timedelta(days=1)
    last30 = orders_between(end - timedelta(days=30), end)
    waits = [o["wait_minutes"] for o in last30]
    by_hour_count = defaultdict(int)
    for o in last30:
        by_hour_count[_parse(o["ts"]).hour] += 1
    peak = sorted(by_hour_count.items(), key=lambda x: -x[1])[:3]
    slow = sorted(by_hour_count.items(), key=lambda x: x[1])[:3]
    return {
        "avg_wait_minutes": round(sum(waits) / max(len(waits), 1), 1),
        "max_wait_minutes": max(waits or [0]),
        "peak_hours":  [{"hour": h, "orders": c} for h, c in peak],
        "slow_hours":  [{"hour": h, "orders": c} for h, c in slow],
    }


# ---------------------------------------------------------------------------
# Revenue root-cause analysis (v1)
#
# "Why did revenue drop?" Instead of a naive vs-yesterday comparison, we build
# a baseline from the SAME weekday over the last 4 weeks at the SAME hour, then
# score the data-backed signals, attribute each to a share of the $ shortfall,
# and summarise the story (demand vs margin).
#
# 3 of the 5 designed signals are always data-backed: traffic, repeat-customer,
# and discount-overuse (Square exposes total_discount_money; mock generates it).
# Cart-abandonment is measurable only when the source exposes checkout sessions
# (the mock source does; a live POS records only placed orders) and
# review-sentiment has no connected source — whatever is unmeasurable on the
# active source is reported as "insufficient_data" and never fabricated. See
# _unavailable_signals().
#
# All times are UTC — consistent with the rest of this module (_today() is UTC
# midnight, order ts are UTC). A real deploy would localise to the restaurant's
# timezone; for the demo, apples-to-apples UTC comparison is what matters.
# ---------------------------------------------------------------------------

# Hand-tuned correlation weights: how strongly an ADVERSE move in each signal
# tends to drive a revenue drop. Traffic (fewer orders) hits revenue hardest and
# most directly; discount-overuse erodes margin; a dip in the returning-customer
# mix is a softer signal.
CAUSE_WEIGHTS = {"traffic": 0.9, "repeat_customer": 0.6, "discount_overuse": 0.7}

# Which direction of each signal is BAD for revenue:
#   traffic / repeat_customer -> a DROP hurts   |   discount_overuse -> a RISE hurts
_ADVERSE = {"traffic": "drop", "repeat_customer": "drop", "discount_overuse": "rise"}

# Designed signals with no usable data source. Surfaced so the AI can honestly
# say "not enough data" instead of inventing a number. cart_abandonment is only
# listed here when the active source lacks a checkout-session stream (see
# _unavailable_signals) — the mock source now provides one, so it's measurable.
_CART_ABANDONMENT_UNAVAILABLE = {
    "signal": "cart_abandonment", "status": "insufficient_data",
    "note": "This POS records only placed/completed orders, not abandoned "
            "checkout sessions — no funnel data exists to measure this."}
_REVIEW_SENTIMENT_UNAVAILABLE = {
    "signal": "review_sentiment", "status": "insufficient_data",
    "note": "No review/sentiment source connected (Square returns no ratings). "
            "Order `rating` exists in mock only — wire a reviews source to enable."}


_PAYMENT_BUCKETS = ("card", "cash", "other")


def _order_payment(o: Dict) -> str | None:
    """The order's payment bucket, or None when the source recorded none."""
    m = (o.get("payment_method") or "").strip().lower()
    return m if m in _PAYMENT_BUCKETS else None


def _item_revenue(o: Dict, item_name: str) -> float:
    """Revenue from `item_name`'s line items inside one order (case-insensitive)."""
    want = item_name.strip().lower()
    return round(sum(li.get("price", 0) * li.get("qty", 0) for li in o.get("items", [])
                     if (li.get("name") or "").strip().lower() == want), 2)


def payment_breakdown(days: int = 30, item_name: str | None = None,
                      start: datetime | None = None, end: datetime | None = None,
                      label: str | None = None) -> Dict:
    """Card/cash/other split on a REVENUE basis — dollars AND percent.

    Scope:
      * item_name=None -> whole-order revenue (order totals).
      * item_name set  -> only that item's line revenue, attributed to the
                          payment method of the order it sold in.

    Orders carrying no payment method (no tender — an OPEN Square order, or any
    source that doesn't record payments) land in `untracked_orders` and are
    EXCLUDED from the split; they are never silently bucketed as "other". When
    `tracked_orders` is 0 the split is empty and `note` says so, so the AI has
    nothing to fabricate a percentage from.

    Percentages are shares of TRACKED revenue only, so revenue_pct sums to 100
    across the three buckets (or all-zero when nothing is tracked).
    """
    if end is None:
        end = _today() + timedelta(days=1)
    if start is None:
        start = end - timedelta(days=days)

    rev = {b: 0.0 for b in _PAYMENT_BUCKETS}
    cnt = {b: 0 for b in _PAYMENT_BUCKETS}
    tracked = untracked = 0

    for o in orders_between(start, end):
        amount = _item_revenue(o, item_name) if item_name else o.get("total", 0)
        if item_name and amount <= 0:
            continue                      # this order didn't contain the item
        bucket = _order_payment(o)
        if bucket is None:
            untracked += 1
            continue
        tracked += 1
        rev[bucket] += amount
        cnt[bucket] += 1

    total = round(sum(rev.values()), 2)
    return {
        "window": label or f"last {days} days",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "item": item_name,
        "basis": "revenue",               # dollars, not order counts
        "tracked_orders": tracked,
        "untracked_orders": untracked,
        "tracked_revenue": total,
        "by_method": [
            {
                "method": b,
                "revenue": round(rev[b], 2),
                "revenue_pct": round(rev[b] / total * 100, 1) if total else 0.0,
                "orders": cnt[b],
            }
            for b in _PAYMENT_BUCKETS
        ],
        "note": (
            "no payment method recorded on this source"
            if tracked == 0 else None
        ),
    }


def payment_context() -> Dict:
    """30-day plus day-scoped payment splits for the AI context."""
    d0 = _today()
    return {
        "payments_30d": payment_breakdown(30, label="last 30 days"),
        "payments_today": payment_breakdown(
            start=d0, end=d0 + timedelta(days=1), label="today"),
        "payments_yesterday": payment_breakdown(
            start=d0 - timedelta(days=1), end=d0, label="yesterday"),
        "payments_this_week": payment_breakdown(
            start=d0 - timedelta(days=d0.weekday()), end=d0 + timedelta(days=1),
            label="this week (Mon-today)"),
    }


def _unavailable_signals() -> List[Dict]:
    """Signals with no data on the ACTIVE source. cart_abandonment drops off this
    list when the source exposes checkout sessions (mock does; live POS doesn't)."""
    out = []
    if not _carts_supported():
        out.append(_CART_ABANDONMENT_UNAVAILABLE)
    out.append(_REVIEW_SENTIMENT_UNAVAILABLE)
    return out


def _same_weekday_baseline_days(lookback_days: int = 28) -> List[datetime]:
    """The same-weekday day-starts within the last `lookback_days` (excl. today).

    For lookback_days=28 this is [today-7, today-14, today-21, today-28] — i.e.
    the last 4 matching weekdays, which is exactly the design's "same weekday,
    average of the last 4 weeks" baseline.
    """
    today = _today()
    return [today - timedelta(days=back) for back in range(7, lookback_days + 1, 7)]


def _orders_upto(day_start: datetime, hour: int, branch_id: str | None = None) -> List[Dict]:
    """Orders on `day_start`'s day from 00:00 up to and INCLUDING `hour`."""
    return orders_between(day_start, day_start + timedelta(hours=hour + 1), branch_id)


def _returning_rate(window_orders: List[Dict], before: datetime) -> float:
    """Share of a window's unique customers who had ordered before `before`.

    This is the "repeat / returning customer" signal: of the people who showed
    up in this window, how many are returning vs brand-new. It moves day-to-day
    (unlike a lifetime visits>=2 flag), which is what makes it a usable signal.
    """
    uniq = {o["customer_id"] for o in window_orders if o.get("customer_id")}
    if not uniq:
        return 0.0
    returning = set()
    for o in _orders():
        cid = o.get("customer_id")
        if cid in uniq and cid not in returning and _parse(o["ts"]) < before:
            returning.add(cid)
    return len(returning) / len(uniq)


def hourly_baseline(hour: int, lookback_days: int = 28, branch_id: str | None = None) -> float:
    """Average revenue in `hour` across the same weekday over the last N weeks.

    Returns the mean revenue booked during [hour, hour+1) on the matching
    baseline days. 0.0 when there is no baseline history. Pass `branch_id` to
    scope the baseline to one branch (used for per-branch incident analysis).
    """
    days = _same_weekday_baseline_days(lookback_days)
    if not days:
        return 0.0
    total = 0.0
    for d in days:
        start = d + timedelta(hours=hour)
        total += sum(o["total"] for o in orders_between(start, start + timedelta(hours=1), branch_id))
    return round(total / len(days), 2)


def detect_anomaly(checkpoint_hour: int, threshold: float = -0.15,
                   branch_id: str | None = None) -> Dict:
    """Flag today if cumulative revenue up to `checkpoint_hour` is below baseline.

    Compares today's revenue from 00:00..checkpoint_hour against the baseline's
    cumulative revenue over the same hours (sum of hourly_baseline). `threshold`
    is a fraction (-0.15 = flag a 15%+ shortfall). Pass `branch_id` to run the
    check for a single branch.
    """
    today = _today()
    today_cum = round(
        sum(o["total"] for o in orders_between(
            today, today + timedelta(hours=checkpoint_hour + 1), branch_id)),
        2,
    )
    baseline_cum = round(
        sum(hourly_baseline(h, branch_id=branch_id) for h in range(0, checkpoint_hour + 1)), 2)
    delta = (today_cum - baseline_cum) / baseline_cum if baseline_cum else 0.0
    return {
        "checkpoint_hour": checkpoint_hour,
        "branch_id": branch_id,
        "today_cumulative_revenue": today_cum,
        "baseline_cumulative_revenue": baseline_cum,
        "delta_pct": round(delta * 100, 1),
        "threshold_pct": round(threshold * 100, 1),
        "flagged": bool(baseline_cum) and delta <= threshold,
    }


def _window_discount_rate(window_orders: List[Dict]) -> float:
    """Effective discount rate for a window = total discount / total subtotal."""
    sub = sum(o.get("subtotal", 0.0) for o in window_orders)
    disc = sum(o.get("discount", 0.0) for o in window_orders)
    return (disc / sub) if sub else 0.0


def _explain(s: Dict) -> str:
    d = s["delta_pct"]
    label = {
        "traffic": f"Order count {s['today_value']} vs {s['baseline_value']} baseline",
        "repeat_customer": f"Returning-customer rate {s['today_value']}% vs {s['baseline_value']}% baseline",
        "discount_overuse": f"Avg discount {s['today_value']}% vs {s['baseline_value']}% baseline",
    }[s["signal"]]
    # adverse_move > 0 means the signal moved in its revenue-hurting direction.
    adverse_move = -d if s["adverse"] == "drop" else d
    contrib = s.get("contribution_pct")
    if adverse_move >= 5:
        verb = "down" if s["adverse"] == "drop" else "up"
        msg = f"{label} — {verb} {abs(d):.0f}%; a likely driver of the revenue drop."
        if contrib:
            msg += f" Explains ~{contrib:.0f}% of today's shortfall."
        if s.get("noisy"):
            msg += " But within normal week-to-week variation — treat as noise, not a confirmed cause."
        return msg
    if adverse_move <= -5:
        verb = "up" if s["adverse"] == "drop" else "down"
        return f"{label} — {verb} {abs(d):.0f}%; not a cause of the drop."
    return f"{label} — roughly flat ({d:+.0f}%); unlikely cause."


def score_causes(checkpoint_hour: int | None = None,
                 branch_id: str | None = None) -> List[Dict]:
    """Rank the data-backed signals by how much each explains a revenue drop.

    For each available signal we compute delta% vs baseline (today up to
    `checkpoint_hour` vs the same-weekday baseline up to the same hour), then
    score = correlation_weight x magnitude of the ADVERSE move. Each signal has
    its own bad direction (traffic/repeat: a drop; discount: a rise), so a move
    the "good" way scores 0 and is not flagged. Returned sorted by score
    descending, so the biggest weighted adverse move ranks #1.

    Beyond the raw score, each signal also carries a `contribution_pct` — an
    arithmetic estimate of how much of today's *dollar* shortfall it explains
    (revenue ≈ orders × AOV): traffic explains the volume loss, discount the
    extra-discount loss. repeat_customer is a leading/correlational indicator
    (contribution_pct = None). Single-day repeat dips inside normal week-to-week
    variation are flagged `noisy` and their score is halved.

    Pass `branch_id` to diagnose one branch (used for per-branch incidents).
    `checkpoint_hour` defaults to the current UTC hour (clamped to business
    hours) for a fair partial-day comparison.
    """
    today = _today()
    if checkpoint_hour is None:
        checkpoint_hour = min(22, max(7, datetime.now(timezone.utc).hour))
    base_days = _same_weekday_baseline_days()
    today_win = _orders_upto(today, checkpoint_hour, branch_id)
    base_wins = [_orders_upto(d, checkpoint_hour, branch_id) for d in base_days]

    def _delta(today_val: float, base_vals: List[float]):
        base = sum(base_vals) / len(base_vals) if base_vals else 0.0
        delta = ((today_val - base) / base * 100) if base else 0.0
        return base, delta

    # --- Traffic: order count ---
    t_base, t_delta = _delta(len(today_win), [len(w) for w in base_wins])
    # --- Repeat customer: returning-customer rate (+ week-to-week noise guard) ---
    r_today = _returning_rate(today_win, today)
    r_rates = [_returning_rate(w, d) for w, d in zip(base_wins, base_days)]
    r_base, r_delta = _delta(r_today, r_rates)
    r_swing = (max(r_rates) - min(r_rates)) if r_rates else 0.0
    # A drop no larger than the historical week-to-week spread is likely noise.
    r_noisy = r_delta < 0 and abs(r_today - r_base) <= r_swing
    # --- Discount overuse: effective discount rate ---
    d_today = _window_discount_rate(today_win)
    d_base, d_delta = _delta(d_today, [_window_discount_rate(w) for w in base_wins])

    # --- Dollar-shortfall attribution (Step 2: "how much does this explain") ---
    today_rev = sum(o["total"] for o in today_win)
    base_rev = sum(sum(o["total"] for o in w) for w in base_wins) / len(base_wins) if base_wins else 0.0
    today_sub = sum(o.get("subtotal", 0.0) for o in today_win)
    rev_drop = base_rev - today_rev
    base_aov = (base_rev / t_base) if t_base else 0.0
    volume_loss = max(0.0, t_base - len(today_win)) * base_aov          # traffic $ impact
    disc_loss = max(0.0, d_today - d_base) * today_sub                  # discount $ impact

    def _contrib(loss: float):
        return round(min(max(loss / rev_drop, 0.0), 1.0) * 100, 1) if rev_drop > 0 else 0.0

    signals = [
        {"signal": "traffic", "today_value": len(today_win),
         "baseline_value": round(t_base, 1), "delta_pct": round(t_delta, 1),
         "contribution_pct": _contrib(volume_loss)},
        {"signal": "repeat_customer", "today_value": round(r_today * 100, 1),
         "baseline_value": round(r_base * 100, 1), "delta_pct": round(r_delta, 1),
         "contribution_pct": None, "noisy": bool(r_noisy)},   # leading indicator
        {"signal": "discount_overuse", "today_value": round(d_today * 100, 1),
         "baseline_value": round(d_base * 100, 1), "delta_pct": round(d_delta, 1),
         "contribution_pct": _contrib(disc_loss)},
    ]
    for s in signals:
        s["weight"] = CAUSE_WEIGHTS[s["signal"]]
        s["adverse"] = _ADVERSE[s["signal"]]
        adverse_move = -s["delta_pct"] if s["adverse"] == "drop" else s["delta_pct"]
        adverse_move = max(0.0, adverse_move)
        if s.get("noisy"):
            adverse_move *= 0.5   # don't over-trust a single noisy day
        s["score"] = round(adverse_move * s["weight"], 1)
        s["explanation"] = _explain(s)
    signals.sort(key=lambda s: s["score"], reverse=True)
    return signals


def _driver_summary(ranked: List[Dict], shortfall: float) -> str:
    """One-line relational read of the shortfall (Step 2's cause-logic table):
    volume-driven demand story vs steady-volume margin story vs mixed."""
    if shortfall <= 0:
        return "Revenue at or above baseline — no shortfall to explain."
    tc = next((s.get("contribution_pct") or 0 for s in ranked if s["signal"] == "traffic"), 0)
    dc = next((s.get("contribution_pct") or 0 for s in ranked if s["signal"] == "discount_overuse"), 0)
    if tc >= 60:
        return (f"Volume explains ~{tc:.0f}% of the ${shortfall:,.0f} shortfall "
                f"— a demand/traffic story.")
    if dc >= 40 and tc < 25:
        return (f"Order volume steady but discounts up — a margin story "
                f"(~{dc:.0f}% of the ${shortfall:,.0f} shortfall), not demand.")
    return (f"Mixed drivers: traffic ~{tc:.0f}%, discount ~{dc:.0f}% of the "
            f"${shortfall:,.0f} shortfall.")


def revenue_diagnosis(checkpoint_hour: int | None = None,
                      branch_id: str | None = None) -> Dict:
    """The full "why did revenue drop" packet injected into restaurant_context."""
    if checkpoint_hour is None:
        checkpoint_hour = min(22, max(7, datetime.now(timezone.utc).hour))
    anomaly = detect_anomaly(checkpoint_hour, branch_id=branch_id)
    causes = score_causes(checkpoint_hour, branch_id=branch_id)
    shortfall = max(0.0, anomaly["baseline_cumulative_revenue"] - anomaly["today_cumulative_revenue"])
    return {
        "checkpoint_hour": checkpoint_hour,
        "branch_id": branch_id,
        "anomaly": anomaly,
        "revenue_shortfall": round(shortfall, 2),
        "driver_summary": _driver_summary(causes, shortfall),
        "ranked_causes": causes,
        "unavailable_signals": _unavailable_signals(),
        "method": ("Baseline = same weekday, avg of last 4 weeks at the same hour. "
                   "Data-backed signals: traffic, repeat-customer, discount-overuse "
                   "(each with a $-shortfall contribution estimate). "
                   "Cart-abandonment & review-sentiment are insufficient_data, "
                   "never fabricated."),
    }


def restaurant_context() -> Dict:
    """Compact, structured snapshot injected into the AI system prompt."""
    today = today_kpis()
    rb = revenue_breakdown(30)
    return {
        "today": today,
        "health": health_score(),
        # Sales/order breakdown so the AI can answer "where do sales come from",
        # channel mix, and peak hours — trimmed to keep the prompt compact.
        "sales_30d": {
            "by_channel": rb["by_channel"],       # revenue per order channel
            "by_hour": rb["by_hour"],             # revenue per hour (7:00–22:00)
            "by_day_14d": rb["by_day"][-14:],     # last 14 days of daily revenue
        },
        "branches_7d": branch_performance(7),
        "top_menu_30d": menu_performance(30)[:5],
        "bottom_menu_30d": menu_performance(30)[-3:],
        "customers": {k: v for k, v in customer_intelligence().items()
                      if k not in ("top_vips", "at_risk_list")},
        "operations": operations_snapshot(),
        "forecast_30d": forecast(30)["projected_revenue"],
        "briefing": daily_briefing(),
        # v1 root-cause analysis for "why did revenue/sales drop" questions.
        # Baseline-driven (same weekday, last 4 weeks) with ranked causes. Only
        # traffic & repeat-customer are data-backed; the rest say insufficient_data.
        "revenue_diagnosis": revenue_diagnosis(),
        # Card/cash/other splits on a revenue basis (dollars + %), 30-day plus
        # today/yesterday/this-week windows so scoped questions don't get a
        # 30-day number. tracked_orders=0 means the source records no payments.
        **payment_context(),
    }
