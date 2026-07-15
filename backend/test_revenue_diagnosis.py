"""
Backtest + validation for the revenue root-cause analysis (analytics.py).

Follows the manager's Step 4: validate against KNOWN incidents before trusting
the classifier. We assemble labelled "incident days" (we already know the
cause) and check the top-ranked cause matches. Gate: if the top cause is wrong
on more than 20% of incidents, FAIL — a wrong root cause is worse than none.

Three parts:
  1. Synthetic labelled incidents (traffic / repeat / discount / mixed).
  2. A REAL incident from mock_data.py — Downtown's engineered ~22% traffic
     drop over the last 7 days — diagnosed branch-scoped, no monkeypatching.
  3. A noise-robustness check — a repeat dip within normal week-to-week
     variation must be flagged `noisy` and down-weighted.

Run from backend/:  python test_revenue_diagnosis.py
"""
import os
from datetime import timedelta

os.environ.setdefault("DATA_SOURCE", "mock")  # avoid any live Square calls on import

import analytics

_ORIG_ORDERS = analytics._orders          # real mock dataset accessor (for part 2)
TODAY = analytics._today()
HOUR = 9                    # all synthetic orders land at 09:00 UTC
CHECKPOINT = 22            # score the full business day, deterministically
SUBTOTAL = 20.0
REGULARS = [f"reg_{i}" for i in range(60)]   # customers with prior history


def _order(cid, day, discount_rate=0.0):
    ts = (day + timedelta(hours=HOUR)).isoformat()
    discount = round(SUBTOTAL * discount_rate, 2)
    return {"id": f"o_{cid}_{ts}", "branch_id": "br_x", "ts": ts,
            "customer_id": cid, "subtotal": SUBTOTAL, "discount": discount,
            "total": round(SUBTOTAL - discount, 2), "items": []}


def _day_orders(day, count, returning_rate, discount_rate, label):
    n_ret = round(count * returning_rate)
    orders = [_order(REGULARS[i], day, discount_rate) for i in range(n_ret)]
    orders += [_order(f"new_{label}_{i}", day, discount_rate) for i in range(count - n_ret)]
    return orders


def build_dataset(today_count, today_returning, today_discount,
                  baseline_returning=(0.5, 0.5, 0.5, 0.5)):
    """Baseline = 4 same-weekdays at count=100, discount=0.10, and the given
    returning rates. `today_*` control the incident day under test."""
    orders = [_order(cid, TODAY - timedelta(days=35)) for cid in REGULARS]  # prior history
    for back, ret in zip((7, 14, 21, 28), baseline_returning):
        orders += _day_orders(TODAY - timedelta(days=back), 100, ret, 0.10, f"b{back}")
    orders += _day_orders(TODAY, today_count, today_returning, today_discount, "today")
    return orders


# name, today_count, today_returning, today_discount, expected top cause
INCIDENTS = [
    ("Traffic drop (-30% orders)",              70, 0.50, 0.10, "traffic"),
    ("Repeat drop (0.5->0.2, real)",           100, 0.20, 0.10, "repeat_customer"),
    ("Discount overuse (10%->40%)",            100, 0.50, 0.40, "discount_overuse"),
    ("Mixed, traffic worst (-40% ord, -30% rep)", 60, 0.35, 0.10, "traffic"),
]


def run_synthetic():
    print("=== Part 1: synthetic labelled incidents ===")
    correct = 0
    for name, cnt, ret, disc, expected in INCIDENTS:
        analytics._orders = lambda ds=build_dataset(cnt, ret, disc): ds
        causes = analytics.score_causes(checkpoint_hour=CHECKPOINT)
        top = causes[0]["signal"]
        ok = top == expected
        correct += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<42} expected={expected:<16} got={top}")
    return correct, len(INCIDENTS)


def run_real_incident():
    print("\n=== Part 2: REAL incident from mock_data.py (Downtown traffic drop) ===")
    analytics._orders = _ORIG_ORDERS   # use the actual mock dataset, no override
    diag = analytics.revenue_diagnosis(checkpoint_hour=CHECKPOINT, branch_id="br_downtown")
    top = diag["ranked_causes"][0]
    ok = top["signal"] == "traffic"
    print(f"  branch=br_downtown  anomaly_flagged={diag['anomaly']['flagged']}  "
          f"shortfall=${diag['revenue_shortfall']:.0f}")
    print(f"  driver_summary: {diag['driver_summary']}")
    print(f"  {'PASS' if ok else 'FAIL'}  expected top=traffic  got={top['signal']} "
          f"(delta={top['delta_pct']}%, contribution={top['contribution_pct']}%)")
    return int(ok), 1


def run_noise_check():
    print("\n=== Part 3: noise robustness (repeat dip within normal variation) ===")
    # Baseline repeat rates swing widely (0.3..0.6); today 0.35 is inside that band.
    analytics._orders = lambda ds=build_dataset(100, 0.35, 0.10,
                                                baseline_returning=(0.3, 0.5, 0.4, 0.6)): ds
    causes = analytics.score_causes(checkpoint_hour=CHECKPOINT)
    rep = next(c for c in causes if c["signal"] == "repeat_customer")
    ok = rep["noisy"] is True
    print(f"  repeat delta={rep['delta_pct']}%  noisy={rep['noisy']}  score={rep['score']} "
          f"(halved when noisy)")
    print(f"  {'PASS' if ok else 'FAIL'}  expected repeat flagged noisy")
    return ok


def run():
    c1, n1 = run_synthetic()
    c2, n2 = run_real_incident()
    noise_ok = run_noise_check()

    correct, total = c1 + c2, n1 + n2
    error_rate = (total - correct) / total
    print(f"\nIncident top-cause accuracy: {correct}/{total} correct "
          f"({error_rate*100:.0f}% wrong; gate = <=20%)")
    passed = error_rate <= 0.20 and noise_ok
    print("RESULT:", "PASS" if passed else "FAIL")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
