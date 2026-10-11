"""backend/app/routers/auth.py - signing up, logging in and out, and "who am
I logged in as?".

The login is kept in a cookie the website can't read. So when the website
loads, it asks /me who's logged in. The browser sends the cookie with every
request by itself.

Not built, and listed here so it's clear: limits on repeated login attempts,
locking accounts after failures, password reset, email confirmation, and
cross-site request tokens. The cookie's SameSite setting already blocks the
most important cross-site attack; a real product would add more protection.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import ROLE_LEVELS
from ..constants import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_NOTICE,
    DEMO_ADMIN_PASSWORD,
    ROLES,
)
from ..deps import get_current_user, get_db
from ..models import Tenant, User
from ..passwords import hash_password, verify_password_or_dummy
from ..schemas import (
    DemoCredentialsOut,
    LoginRequest,
    MeOut,
    SignupRequest,
    TenantOut,
)
from ..tokens import clear_session_cookie, issue_token, set_session_cookie

router = APIRouter(prefix="/auth", tags=["auth"])

# The same message for "no such account" and "wrong password". Different
# messages would let anyone find out which emails have accounts.
# passwords.verify_password_or_dummy also makes both take the same time.
_BAD_CREDENTIALS = "incorrect email or password"


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        role_label=ROLES[user.role]["label"],
        tenant_slug=user.tenant.slug if user.tenant_id is not None else None,
        tenant_name=user.tenant.name if user.tenant_id is not None else None,
    )


@router.get("/tenants", response_model=list[TenantOut])
def signup_tenants(db: Session = Depends(get_db)):
    """The list of companies, for the signup form's dropdown.

    It has to work without logging in, because people choose a company before
    they have an account. It's a separate address from the main company list,
    so it's obvious that this one is public. It only sends each company's name
    and ID - nothing else.
    """
    return db.query(Tenant).order_by(Tenant.name).all()


@router.get("/demo-credentials", response_model=DemoCredentialsOut)
def demo_credentials():
    """The demo admin login details, for the login page to show.

    Sent from the same place that creates the account, so what the page shows
    always matches the real login.
    """
    return DemoCredentialsOut(
        email=DEMO_ADMIN_EMAIL,
        password=DEMO_ADMIN_PASSWORD,
        notice=DEMO_ADMIN_NOTICE,
    )


@router.post("/signup", response_model=MeOut, status_code=201)
def signup(body: SignupRequest, response: Response, db: Session = Depends(get_db)):
    """Create an account at an existing company and log in straight away.

    Signing up can't create a new company. Orders are loaded per company, so a
    new one would have no orders, alerts or history. Only the platform admin
    can add companies, through POST /api/tenants.

    Signing up also can't make you a platform admin - that's refused
    automatically. It CAN make you a company admin at any company, which is
    deliberately open for this demo; see DEMO_ADMIN_NOTICE.
    """
    tenant = db.query(Tenant).filter(Tenant.slug == body.tenant_slug).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"unknown tenant '{body.tenant_slug}'")

    if db.query(User).filter(User.email == body.email).first() is not None:
        raise HTTPException(status_code=409, detail="an account with that email already exists")

    user = User(
        email=body.email,  # already put in lower case by the schema
        password_hash=hash_password(body.password),
        display_name=(body.display_name or "").strip() or body.email.split("@")[0],
        role=body.role,
        tenant_id=tenant.id,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Someone else signed up with this email at the same moment.
        db.rollback()
        raise HTTPException(status_code=409, detail="an account with that email already exists")
    db.refresh(user)

    set_session_cookie(response, issue_token(user.id, user.role, tenant.slug, user.email))
    return _me(user)


@router.post("/login", response_model=MeOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()

    # Runs a password check whether or not the account exists, so both cases
    # take the same time as well as giving the same message.
    if not verify_password_or_dummy(body.password, user.password_hash if user else None):
        raise HTTPException(status_code=401, detail=_BAD_CREDENTIALS)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="this account has been deactivated")
    if user.role not in ROLE_LEVELS:
        # Also checked in deps.get_current_user. Without this check, looking up
        # the role's display name below would crash, and the user would see a
        # server error instead of being told their account is broken.
        raise HTTPException(
            status_code=403,
            detail=f"account has unknown role '{user.role}' - must be one of {list(ROLE_LEVELS)}",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    tenant_slug = user.tenant.slug if user.tenant_id is not None else None
    set_session_cookie(response, issue_token(user.id, user.role, tenant_slug, user.email))
    return _me(user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    """Log out. Always succeeds - logging out when you're not logged in isn't
    an error, you're already where you wanted to be."""
    clear_session_cookie(response)
    return Response(status_code=204, headers=dict(response.headers))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    """Who's logged in. The website can't read the login cookie itself, so
    this is how it finds out."""
    return _me(user)
