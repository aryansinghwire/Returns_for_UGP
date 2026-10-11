"""backend/app/services/dates.py - decides what "today" means for this data.

The order dates are made up (see serving/config.py) - the original data has no
dates, so they're spread across October and November 2021. The real date today
is years after that, so "the last 7 days" counted from today would find nothing.

So the dashboard's "today" is the newest order in the data being viewed. Both
the order list's date filter and the alerts use this one rule, so they always
agree.

This means "today" can differ between users. The platform admin, looking at
every company, may have a later "today" than an analyst at one company, if
that company's newest order is older. Each sees the newest order they can
actually see - which is why the date range is always sent back to the website,
not guessed by it.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Order

DATE_FORMAT = "%Y-%m-%d"

# The longest date range anyone can ask for. The data covers 61 days; a year
# leaves room for bigger datasets, while still catching a typo like 99999 that
# would quietly mean "no filter". Kept here so every date filter uses the same
# limit.
MAX_PERIOD_DAYS = 365


def latest_order_date(db: Session, tenant_id: Optional[int] = None) -> Optional[str]:
    """The newest order date this user can see (like "2021-11-29"), or None if
    they can't see any orders."""
    q = db.query(func.max(Order.order_date))
    if tenant_id is not None:
        q = q.filter(Order.tenant_id == tenant_id)
    return q.scalar()


def window_start(end_date: str, n_days: int) -> str:
    """The first day of an N-day period ending on `end_date`.

    "The last 7 days" includes the end day itself, so it starts 6 days before.
    Both the first and last day count.
    """
    end = datetime.strptime(end_date, DATE_FORMAT).date()
    return (end - timedelta(days=n_days - 1)).isoformat()


def recent_window(db: Session, tenant_id: Optional[int], n_days: int):
    """The first and last day of the most recent N days, or (None, None) if
    there are no orders."""
    end = latest_order_date(db, tenant_id)
    if end is None:
        return None, None
    return window_start(end, n_days), end
