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
    return {
        "revenue":          round(revenue, 2),
        "subtotal":         round(subtotal, 2),
        "orders":           count,
        "customers":        unique_customers,
        "avg_order_value":  round(aov, 2),
        "tips":             round(tips, 2),
        "gross_margin":     round((subtotal - cost) / subtotal * 100, 1) if subtotal else 0.0,
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
        "vs_yesterday_pct": _pct(today_k["revenue"], yest_k["revenue"]),
        "vs_last_week_pct": _pct(today_k["revenue"], lw_k["revenue"]),
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


def restaurant_context() -> Dict:
    """Compact, structured snapshot injected into the AI system prompt."""
    today = today_kpis()
    return {
        "today": today,
        "health": health_score(),
        "branches_7d": branch_performance(7),
        "top_menu_30d": menu_performance(30)[:5],
        "bottom_menu_30d": menu_performance(30)[-3:],
        "customers": {k: v for k, v in customer_intelligence().items()
                      if k not in ("top_vips", "at_risk_list")},
        "operations": operations_snapshot(),
        "forecast_30d": forecast(30)["projected_revenue"],
        "briefing": daily_briefing(),
    }
