"""backend/tests/test_auth.py - tests for signing up, logging in and out, and
checking who's allowed to do what.

Two older tests checked things that could only be faked using special request
headers, which no longer exist. What they really checked - that someone with no
company is refused, and that an unknown role can't do anything - is tested
below in the ways that are still possible.
"""

import jwt
import pytest

from backend.app.config import JWT_ALGORITHM, JWT_SECRET, SESSION_COOKIE_NAME
from backend.app.constants import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD
from backend.app.models import User
from backend.tests.conftest import (
    ANALYST_EMAIL,
    PASSWORD,
    login_client,
    make_user,
)

SIGNUP = {
    "tenant_slug": "test-tenant",
    "email": "newbie@test-tenant.test",
    "password": "a-good-enough-password",
    "role": "ops_analyst",
}


# --- pages anyone can reach without logging in -------------------------------

def test_the_public_surface_is_exactly_what_it_should_be(anon):
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/auth/tenants").status_code == 200
    assert anon.get("/api/auth/demo-credentials").status_code == 200


def test_signup_tenants_lists_tenants_before_there_is_a_session(anon):
    """The signup form's list of companies must load before you have an account."""
    rows = anon.get("/api/auth/tenants").json()
    assert {t["slug"] for t in rows} >= {"test-tenant", "other-tenant"}
    assert set(rows[0]) == {"id", "name", "slug"}, "no extra fields leak here"


def test_demo_credentials_match_the_account_that_is_actually_seeded(anon):
    """The login page shows these details. If they didn't match the real demo
    account, the first thing a visitor tried would fail."""
    creds = anon.get("/api/auth/demo-credentials").json()
    assert creds["email"] == DEMO_ADMIN_EMAIL
    assert creds["password"] == DEMO_ADMIN_PASSWORD
    assert "PROTOTYPE" in creds["notice"]

    r = anon.post("/api/auth/login", json={"email": creds["email"], "password": creds["password"]})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


# --- the most important checks: no login, no access ------------------------

def test_an_unauthenticated_request_is_401_not_a_silent_analyst(anon):
    """Someone who isn't logged in must be refused - never treated as the
    lowest role by default."""
    r = anon.get("/api/orders")
    assert r.status_code == 401
    assert "items" not in r.text


def test_the_x_role_header_is_ignored(analyst):
    """An analyst can't claim admin powers by sending a request header - they
    only get what their account in the database says."""
    assert analyst.get("/api/orders", headers={"X-Role": "admin"}).status_code == 200
    rows = analyst.get("/api/rules", headers={"X-Role": "admin"}).json()
    assert {row["tenant_slug"] for row in rows} <= {"test-tenant"}

    refused = analyst.post(
        "/api/rules?tenant=other-tenant",
        json={"name": "x", "score_min": 0.1, "score_max": 0.2, "action_type": "call_customer"},
        headers={"X-Role": "admin", "X-Actor-Tenant": "other-tenant"},
    )
    assert refused.status_code == 403


def test_an_escalated_role_claim_in_a_valid_token_is_ignored(analyst, db_session):
    """The role is read from the database every time, never from the login
    token. So even a genuine, correctly signed token that says "admin" gets
    nothing extra."""
    user = db_session.query(User).filter(User.email == ANALYST_EMAIL).one()
    forged = jwt.encode(
        {"sub": str(user.id), "role": "admin", "tenant": None,
         "email": user.email, "exp": 2 ** 31 - 1},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    analyst.cookies.set(SESSION_COOKIE_NAME, forged)

    me = analyst.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "ops_analyst", "the claim must not win over the row"
    assert me.json()["tenant_slug"] == "test-tenant"


# --- signup -----------------------------------------------------------------

def test_signup_creates_an_account_and_signs_it_in(anon):
    r = anon.post("/api/auth/signup", json=SIGNUP)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == SIGNUP["email"]
    assert body["role"] == "ops_analyst"
    assert body["tenant_slug"] == "test-tenant"
    assert SESSION_COOKIE_NAME in anon.cookies

    # Logged in straight away - no extra step.
    assert anon.get("/api/orders").status_code == 200


def test_signup_cannot_self_assign_the_platform_admin_role(anon, db_session):
    r = anon.post("/api/auth/signup", json={**SIGNUP, "email": "sneaky@test-tenant.test",
                                            "role": "admin"})
    assert r.status_code == 422
    assert db_session.query(User).filter(User.email == "sneaky@test-tenant.test").first() is None


def test_signup_rejects_an_unknown_tenant(anon):
    r = anon.post("/api/auth/signup", json={**SIGNUP, "email": "nowhere@x.test",
                                             "tenant_slug": "no-such-tenant"})
    assert r.status_code == 404


def test_signup_rejects_a_duplicate_email_regardless_of_case(anon):
    """SQLite treats capital letters as different, so this only works because
    email addresses are put in lower case when saved."""
    first = anon.post("/api/auth/signup", json={**SIGNUP, "email": "dup@test-tenant.test"})
    assert first.status_code == 201

    again = TestClientFactory()
    r = again.post("/api/auth/signup", json={**SIGNUP, "email": "DUP@Test-Tenant.TEST"})
    assert r.status_code == 409


def test_signup_rejects_a_short_password(anon):
    r = anon.post("/api/auth/signup", json={**SIGNUP, "email": "weak@test-tenant.test",
                                             "password": "short"})
    assert r.status_code == 422


def test_a_signed_up_tenant_admin_cannot_touch_another_tenant(anon):
    r = anon.post("/api/auth/signup", json={
        "tenant_slug": "test-tenant", "email": "ta@test-tenant.test",
        "password": "a-good-enough-password", "role": "tenant_admin",
    })
    assert r.status_code == 201
    refused = anon.post(
        "/api/rules?tenant=other-tenant",
        json={"name": "x", "score_min": 0.1, "score_max": 0.2, "action_type": "call_customer"},
    )
    assert refused.status_code == 403


# --- logging in and out -----------------------------------------------------

def test_wrong_password_and_unknown_email_are_indistinguishable(anon):
    """If these looked different, anyone could find out which email addresses
    have accounts."""
    wrong_password = anon.post("/api/auth/login",
                               json={"email": ANALYST_EMAIL, "password": "not-the-password"})
    no_such_user = anon.post("/api/auth/login",
                             json={"email": "ghost@test-tenant.test", "password": PASSWORD})

    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json() == no_such_user.json()


def test_login_sets_an_httponly_session_cookie(anon):
    r = anon.post("/api/auth/login", json={"email": ANALYST_EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"]
    assert SESSION_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


def test_logout_clears_the_cookie_and_the_session(analyst):
    assert analyst.get("/api/orders").status_code == 200
    assert analyst.post("/api/auth/logout").status_code == 204
    assert not analyst.cookies.get(SESSION_COOKIE_NAME)
    assert analyst.get("/api/orders").status_code == 401


def test_logout_without_a_session_is_not_an_error(anon):
    """Logging out when you're not logged in isn't an error - you're already
    logged out."""
    assert anon.post("/api/auth/logout").status_code == 204


# --- broken or forged logins -----------------------------------------------

@pytest.mark.parametrize("name,token", [
    ("garbage", "not-a-jwt-at-all"),
    ("tampered", jwt.encode({"sub": "1", "exp": 2 ** 31 - 1}, "the-wrong-key",
                            algorithm=JWT_ALGORITHM)),
    ("expired", jwt.encode({"sub": "1", "exp": 1_000_000}, JWT_SECRET,
                           algorithm=JWT_ALGORITHM)),
    ("no such user", jwt.encode({"sub": "999999", "exp": 2 ** 31 - 1}, JWT_SECRET,
                                algorithm=JWT_ALGORITHM)),
])
def test_an_unusable_cookie_is_401(anon, name, token):
    anon.cookies.set(SESSION_COOKIE_NAME, token)
    r = anon.get("/api/orders")
    assert r.status_code == 401, name


def test_a_deactivated_account_cannot_use_an_existing_session(analyst, db_session):
    """Whether an account is active is checked on every request, not just at
    login - that's why the server looks the user up each time."""
    user = db_session.query(User).filter(User.email == ANALYST_EMAIL).one()
    user.is_active = 0
    db_session.commit()
    try:
        assert analyst.get("/api/orders").status_code == 401
    finally:
        user.is_active = 1
        db_session.commit()


# --- what the two older tests were really checking -------------------------

def test_a_scoped_user_with_no_tenant_cannot_be_created(db_session):
    """A user who should belong to a company but doesn't must be refused.

    The database won't even store such a user - the ck_users_role_tenant rule
    forbids it. So the check in deps.get_scoped_tenant_or_none can't normally be
    reached. It's kept anyway, as a second line of defence.
    """
    from sqlalchemy.exc import IntegrityError

    make_user(db_session, "orphan@nowhere.test", "ops_analyst", None)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_a_role_the_system_does_not_know_cannot_act(db_session):
    """A user with a role that doesn't exist must be refused. That can only
    happen if the database is edited by hand, and there are two ways it could
    show up."""
    make_user(db_session, "weird@test-tenant.test", "not_a_role", "test-tenant")
    db_session.commit()
    try:
        # 1. They can't log in at all.
        c = TestClientFactory()
        r = c.post("/api/auth/login",
                   json={"email": "weird@test-tenant.test", "password": PASSWORD})
        assert r.status_code == 403
        assert "unknown role" in r.json()["detail"]
    finally:
        db_session.query(User).filter(User.email == "weird@test-tenant.test").delete()
        db_session.commit()


def test_a_role_that_goes_bad_mid_session_stops_working(analyst, db_session):
    """The second way: the user logged in while their role was fine, and it
    was changed afterwards. The role is checked on every request, so the very
    next one is refused - they don't keep access until their login expires."""
    user = db_session.query(User).filter(User.email == ANALYST_EMAIL).one()
    user.role = "not_a_role"
    db_session.commit()
    try:
        r = analyst.get("/api/orders")
        assert r.status_code == 403
        assert "unknown role" in r.json()["detail"]
    finally:
        user.role = "ops_analyst"
        db_session.commit()


def TestClientFactory():
    """A new client that isn't logged in. Made by a function rather than shared,
    because these tests need a second client with its own separate login."""
    from fastapi.testclient import TestClient

    from backend.app.main import app
    return TestClient(app)


__all__ = ["login_client"]
