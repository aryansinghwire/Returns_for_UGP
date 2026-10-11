"""backend/app/bootstrap.py - makes sure the demo admin account exists.

It's called from three places, and each one is needed:

  * main.py, when the server starts - run_dev.sh doesn't reload an existing
    database, so an old database might have no users at all;
  * scripts/seed_db.py - a fresh reload deletes every table, users included;
  * the tests - so they use the real demo account, not a copy of it.

The account is defined once, here, so all three get the same one.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .constants import (
    DEMO_ADMIN_DISPLAY_NAME,
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    LEGACY_DEMO_ADMIN_EMAIL,
)
from .models import User
from .passwords import hash_password


def ensure_demo_admin(db: Session) -> User:
    """Create the demo admin if it's missing, or fix it if it's been changed.
    Safe to run any number of times.

    It doesn't re-scramble the password if the account already exists - that
    is deliberately slow, and would slow down every restart for no reason.
    """
    user = db.query(User).filter(User.email == DEMO_ADMIN_EMAIL).first()

    if user is None:
        # An older database has this account under its old email address.
        # Update that account rather than creating a second one - otherwise
        # there'd be two working admin logins, and nobody would know about one.
        legacy = db.query(User).filter(User.email == LEGACY_DEMO_ADMIN_EMAIL).first()
        if legacy is not None:
            legacy.email = DEMO_ADMIN_EMAIL
            legacy.password_hash = hash_password(DEMO_ADMIN_PASSWORD)
            legacy.display_name = DEMO_ADMIN_DISPLAY_NAME
            legacy.role = "admin"
            legacy.tenant_id = None
            legacy.is_active = 1
            return legacy

        user = User(
            email=DEMO_ADMIN_EMAIL,
            password_hash=hash_password(DEMO_ADMIN_PASSWORD),
            display_name=DEMO_ADMIN_DISPLAY_NAME,
            role="admin",
            tenant_id=None,  # the platform admin belongs to no single company
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            # Another copy of the server created it at the same moment - use theirs.
            db.rollback()
            return db.query(User).filter(User.email == DEMO_ADMIN_EMAIL).one()
        return user

    # The account exists: put back anything that's been changed. Each field is
    # checked first, so nothing is saved when nothing has changed.
    if user.role != "admin":
        user.role = "admin"
    if user.tenant_id is not None:
        user.tenant_id = None
    if not user.is_active:
        user.is_active = 1
    return user
