"""backend/app/routers/tenants.py - listing companies, and adding new ones."""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db, require_role
from ..models import Tenant, User
from ..schemas import TenantCreate, TenantOut

router = APIRouter(prefix="/tenants", tags=["tenants"])


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.get("", response_model=list[TenantOut])
def list_tenants(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The companies this user can see. Only the platform admin sees all of
    them; everyone else sees just their own. (The signup form gets its list
    separately, from GET /api/auth/tenants.)
    """
    q = db.query(Tenant)
    if user.role != "admin":
        q = q.filter(Tenant.id == user.tenant_id)
    return q.order_by(Tenant.name).all()


@router.post("", response_model=TenantOut, status_code=201)
def create_tenant(
    body: TenantCreate,
    db: Session = Depends(get_db),
    role: str = Depends(require_role("admin")),
):
    slug = slugify(body.name)
    if db.query(Tenant).filter(Tenant.slug == slug).first() is not None:
        raise HTTPException(status_code=409, detail=f"tenant with slug '{slug}' already exists")
    tenant = Tenant(name=body.name, slug=slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
