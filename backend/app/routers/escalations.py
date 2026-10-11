"""backend/app/routers/escalations.py - orders an analyst has passed up to their
company admin.

Only company admins and the platform admin can see this list. Analysts raise
escalations but don't work through them - that's the point of passing them
up. Each company admin sees only their own company's; the platform admin sees
everyone's.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db, get_scoped_tenant_or_none, require_role
from ..models import Tenant
from ..schemas import EscalationOut
from ..services.escalations import list_escalations

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_model=list[EscalationOut])
def get_escalations(
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    include_resolved: bool = Query(
        default=False,
        description="also return escalations that already have a recorded outcome",
    ),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("tenant_admin")),
):
    return [EscalationOut(**row) for row in list_escalations(db, tenant, include_resolved)]
