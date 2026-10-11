"""backend/app/services/alerts.py - spots groups of orders being returned more
often than usual.

A deliberately simple check, not a proper statistical test. For each company
and group, it compares the recent return rate with the group's normal rate. It
raises an alert if the gap is big enough AND there are enough recent orders to
trust it. (There are only 397 products in the test data, so small groups would
otherwise trigger alerts just by chance.)

"Recent" counts back from the newest order in the data, not from today - see
services/dates.py for why.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import ALERT_HIGH_GAP, ALERT_MIN_GAP, ALERT_MIN_N, ALERT_WINDOW_DAYS
from ..models import Order, Tenant
from .dates import recent_window
from .reporting import get_baseline_rate

# The kinds of group to check: all orders for one product, one country, or
# one product type.
COHORT_COLUMNS = {
    "product": Order.product_ref,
    "country": Order.country_bucket,
    "product_type": Order.product_type_bucket,
}


def _alerts_for_tenant(db: Session, tenant: Tenant, min_gap: float, min_n: int) -> list[dict]:
    start, end = recent_window(db, tenant.id, ALERT_WINDOW_DAYS)
    if start is None:
        return []

    alerts = []
    for cohort_type, col in COHORT_COLUMNS.items():
        keys = [
            row[0] for row in
            db.query(col).filter(Order.tenant_id == tenant.id).distinct().all()
        ]
        for key in keys:
            window_q = (
                db.query(func.count(Order.order_id), func.avg(Order.is_returned_ground_truth))
                .filter(
                    Order.tenant_id == tenant.id,
                    col == key,
                    Order.order_date >= start,
                    Order.order_date <= end,
                )
            )
            n, actual_rate = window_q.one()
            n = int(n or 0)
            if n < min_n:
                continue
            actual_rate = float(actual_rate or 0.0)

            baseline_rate, _ = get_baseline_rate(db, tenant.id, cohort_type, key)
            gap = actual_rate - baseline_rate
            if gap >= min_gap:
                alerts.append({
                    "tenant": tenant.name,
                    "cohort_type": cohort_type,
                    "cohort_key": key,
                    "baseline_rate": baseline_rate,
                    "actual_rate": actual_rate,
                    "gap": gap,
                    "n_orders": n,
                    "severity": "high" if gap >= ALERT_HIGH_GAP else "medium",
                })
    return alerts


def get_alerts(db: Session, tenant: Tenant | None, min_gap: float = ALERT_MIN_GAP,
                min_n: int = ALERT_MIN_N) -> list[dict]:
    tenants = [tenant] if tenant is not None else db.query(Tenant).all()
    out = []
    for t in tenants:
        out.extend(_alerts_for_tenant(db, t, min_gap, min_n))
    out.sort(key=lambda a: -a["gap"])
    return out
