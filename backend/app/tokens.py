"""backend/app/tokens.py - creates and checks login tokens, and the cookie
that holds them.

The token is kept in a cookie the website's own code can't read. That's
safer than storing it where JavaScript can reach it: if a malicious script
ever got onto the page, it couldn't steal the login.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Response

from .config import (
    JWT_ALGORITHM,
    JWT_SECRET,
    JWT_TTL_SECONDS,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
)


def issue_token(user_id: int, role: str, tenant_slug: Optional[str], email: str) -> str:
    """Create a login token.

    The role, company and email are included only to make tokens easy to read
    when debugging. The server never trusts them - deps.get_current_user looks
    the user up fresh on every request, so a role change or a disabled account
    takes effect immediately, not when the token expires.
    """
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),  # the token standard requires this to be text
            "role": role,
            "tenant": tenant_slug,
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=JWT_TTL_SECONDS)).timestamp()),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """Check a token is genuine and read it. Raises jwt.PyJWTError if anything
    is wrong.

    The signing method is named explicitly. Leaving it open is a known security
    hole: an attacker could send a token claiming it needs no signature.
    """
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=JWT_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
        path="/",
        # No domain is set, on purpose. The cookie then belongs to whatever
        # address the browser used (localhost:5173 in development) and gets sent
        # back correctly. Setting a domain like "127.0.0.1" would make the browser
        # ignore it - login would seem to work, then every request would fail.
    )


def clear_session_cookie(response: Response) -> None:
    # These settings must match set_session_cookie exactly. If they don't, the
    # browser treats this as a different cookie and keeps the user logged in.
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
    )
