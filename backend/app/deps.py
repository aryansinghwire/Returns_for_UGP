"""backend/app/deps.py - works out who is making each request, and what they
may see and do.

This is the only place the app decides who someone is. It reads the login
cookie, looks the user up in the database, and checks their role and company.

Anyone logged in may read data. Only endpoints that change data call
require_role(...) to check the caller is allowed to.

WARNING: DON'T DELETE THE `role` LINE ON ENDPOINTS. Many endpoints have

    role: str = Depends(require_role("tenant_admin")),

and then never use `role`. It looks unused, but it is the permission check.
FastAPI runs it before the endpoint itself, and refuses the request if the
role is too low. Delete it and the endpoint still works - but now anyone
logged in can use it, and tests that only check the success case won't
notice. Fifteen endpoints look like this.

The same goes for `tenant: ... = Depends(get_scoped_tenant_or_none)` when the
endpoint ignores the value: running it is what stops someone asking for
another company's data.
"""

from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .config import ROLE_LEVELS, SESSION_COOKIE_NAME
from .db import get_db
from .models import Tenant, User
from .tokens import decode_token

# One message for every kind of bad login. Saying whether it was expired,
# forged or for a deleted user would help an attacker, and wouldn't help a
# real user - the fix is the same either way: log in again.
_INVALID_SESSION = "session expired or invalid"


def _no_tenant(role: str) -> HTTPException:
    """The error for a user who should belong to a company but doesn't.

    Normal signup can't create this - the database forbids it - so it only
    happens if someone edits the database by hand. Say that clearly, rather
    than reporting a missing company called ""."""
    return HTTPException(
        status_code=403,
        detail=(f"role '{role}' is tenant-scoped but the signed-in account "
                f"has no tenant"),
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Return the logged-in user, or refuse with 401.

    401 means "you're not logged in". It's kept separate from 403 ("you're not
    allowed") so the website knows whether to show the login page.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")

    try:
        claims = decode_token(token)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail=_INVALID_SESSION)

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail=_INVALID_SESSION)

    if user.role not in ROLE_LEVELS:
        # Someone has edited the database to give this user a role that
        # doesn't exist. Refuse, rather than quietly treating them as the
        # lowest role - that would hide the mistake.
        raise HTTPException(
            status_code=403,
            detail=f"account has unknown role '{user.role}' - must be one of {list(ROLE_LEVELS)}",
        )
    return user


def get_role(user: User = Depends(get_current_user)) -> str:
    """The user's role, read fresh from the database.

    Not taken from the login token on purpose. A token can be up to eight hours
    old, so a user who'd been demoted or disabled would keep their old access
    until it expired. Reading the database costs one quick lookup per request.
    """
    return user.role


def get_actor_tenant(user: User = Depends(get_current_user)) -> Optional[str]:
    """The company the user *belongs to* - which may differ from the company
    they're asking about in `?tenant=`.

    None means the platform admin, who can see every company. Nobody else is
    ever None.
    """
    return user.tenant.slug if user.tenant_id is not None else None


def require_role(min_role: str):
    min_level = ROLE_LEVELS[min_role]

    def _check(role: str = Depends(get_role)) -> str:
        if ROLE_LEVELS[role] < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"role '{role}' cannot perform this action (requires >= '{min_role}')",
            )
        return role

    return _check


def _lookup(db: Session, slug: str) -> Tenant:
    """Find a company by its short name, or refuse with 404."""
    row = db.query(Tenant).filter(Tenant.slug == slug).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown tenant '{slug}'")
    return row


def get_tenant_or_404(
    tenant: str = Query(..., description="tenant slug"),
    db: Session = Depends(get_db),
) -> Tenant:
    """Find the company named in `?tenant=`, for endpoints that require it.

    This only finds the company. It doesn't check whether the user is allowed
    to see it - require_tenant_scope does that."""
    return _lookup(db, tenant)


def require_tenant_scope(
    tenant: Tenant = Depends(get_tenant_or_404),
    role: str = Depends(get_role),
    actor_tenant: Optional[str] = Depends(get_actor_tenant),
) -> Tenant:
    """Find the requested company and check the user may act on it.

    The platform admin may act on any company. Everyone else is limited to
    their own - an admin at Aurora Apparel can't see or change Nimbus Fashion
    Co.'s settings.
    """
    if role == "admin":
        return tenant
    if actor_tenant is None:
        raise _no_tenant(role)
    if actor_tenant != tenant.slug:
        raise HTTPException(
            status_code=403,
            detail=(f"role '{role}' is scoped to tenant '{actor_tenant}' and cannot "
                    f"act on tenant '{tenant.slug}'"),
        )
    return tenant


def get_scoped_tenant_or_none(
    tenant: Optional[str] = Query(default=None, description="tenant slug"),
    role: str = Depends(get_role),
    actor_tenant: Optional[str] = Depends(get_actor_tenant),
    db: Session = Depends(get_db),
) -> Optional[Tenant]:
    """Work out which company's data this request may see.

    The platform admin may name a company with ?tenant=, or leave it out to see
    all of them. Everyone else only ever sees their own company, whatever
    ?tenant= says - asking for a different one is refused. Because the server
    enforces this, it doesn't matter what the website sends.
    """
    if role == "admin":
        return _lookup(db, tenant) if tenant is not None else None

    if actor_tenant is None:
        raise _no_tenant(role)
    if tenant is not None and tenant != actor_tenant:
        raise HTTPException(
            status_code=403,
            detail=(f"role '{role}' is scoped to tenant '{actor_tenant}' and cannot "
                    f"view tenant '{tenant}'"),
        )
    return _lookup(db, actor_tenant)
