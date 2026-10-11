"""backend/app/routers/dashboard.py - the numbers on the dashboard's front page.

Lives at /api/dashboard rather than under /orders. Anything under /orders has
to be listed above the /{order_id} route, or the server mistakes it for an
order number - a separate address avoids that trap entirely.

Anyone logged in can see it. The full escalations list is limited to company
admins, because working through it is their job. But a simple count of open
escalations isn't that list, and the analyst who raised them can already see
each one on its order.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db, get_role, get_scoped_tenant_or_none
from ..models import Tenant
from ..schemas import DashboardOut
from ..services.dashboard import get_dashboard
from ..services.dates import MAX_PERIOD_DAYS

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def read_dashboard(
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    last_n_days: Optional[int] = Query(
        default=None, ge=1, le=MAX_PERIOD_DAYS,
        description=("trailing window for the ORDERS section only - the actions "
                     "section is all time by design, because order dates are "
                     "synthetic and end in Nov 2021 while intervention timestamps "
                     "are real wall-clock time"),
    ),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    return DashboardOut(**get_dashboard(db, tenant, last_n_days))
