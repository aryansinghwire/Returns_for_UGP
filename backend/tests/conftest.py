"""backend/tests/conftest.py - shared setup for the tests: a throwaway
database, some test users, and logged-in clients for each role.

pytest runs this file before any test file in this folder, so it's the safest
place to point the tests at the throwaway database before anything else
connects to the real one.
"""

import os
import tempfile

TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "rto_dashboard_test.db")
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)
# Must be set BEFORE anything from backend.app is loaded, because db.py
# connects to the database as soon as it loads.
os.environ["RETURNS_DASHBOARD_DB_URL"] = f"sqlite:///{TEST_DB_PATH}"
# Password scrambling normally takes about a quarter of a second, and the
# tests do it dozens of times. So the tests make it quicker. Nothing else
# changes, and the real setting in passwords.py is untouched.
os.environ.setdefault("RETURNS_DASHBOARD_BCRYPT_ROUNDS", "4")
# At least 32 characters long, or the login library warns that the key is short.
os.environ.setdefault(
    "RETURNS_DASHBOARD_JWT_SECRET", "test-secret-used-nowhere-else-and-long-enough"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.bootstrap import ensure_demo_admin  # noqa: E402
from backend.app.constants import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD  # noqa: E402
from backend.app.db import Base, SessionLocal, engine  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models import Order, OrderStatus, Tenant, User  # noqa: E402
from backend.app.passwords import hash_password  # noqa: E402

Base.metadata.create_all(bind=engine)

PASSWORD = "test-password-123"
ANALYST_EMAIL = "analyst@test-tenant.test"
TENANT_ADMIN_EMAIL = "tenant-admin@test-tenant.test"
OTHER_ANALYST_EMAIL = "analyst@other-tenant.test"


def make_user(db, email, role, tenant_slug, password=PASSWORD):
    """Add a user directly to the database.

    These users are just there for other tests to use, so they skip the signup
    page - test_auth.py is where signup itself is tested. It also lets the
    tests make users that signup can't (like a platform admin).
    """
    tenant_id = None
    if tenant_slug is not None:
        tenant_id = db.query(Tenant.id).filter(Tenant.slug == tenant_slug).scalar()
        assert tenant_id is not None, f"tenant '{tenant_slug}' must be seeded first"
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=email.split("@")[0],
        role=role,
        tenant_id=tenant_id,
        is_active=1,
    )
    db.add(user)
    return user


@pytest.fixture(scope="session", autouse=True)
def seed_minimal():
    db = SessionLocal()
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    other = Tenant(name="Other Tenant", slug="other-tenant")
    db.add_all([tenant, other])
    db.flush()

    order = Order(
        order_id="TEST-ORD-000001", tenant_id=tenant.id, customer_ref="c1", product_ref="p1",
        order_date="2021-10-15", model_risk_score=0.9, reasons_json='["high risk"]',
        customer_no_history=0, product_no_history=0, customer_return_rate=0.8,
        product_return_rate=0.6, avg_discount_value=10.0, avg_gbp_price=20.0,
        country_bucket="Country_A", product_brand_bucket="Brand_A",
        product_type_bucket="productType_A", raw_features_json="{}",
        is_returned_ground_truth=1,
    )
    db.add(order)
    db.add(OrderStatus(order_id=order.order_id, current_score=0.9, status="pending"))

    make_user(db, ANALYST_EMAIL, "ops_analyst", "test-tenant")
    make_user(db, TENANT_ADMIN_EMAIL, "tenant_admin", "test-tenant")
    make_user(db, OTHER_ANALYST_EMAIL, "ops_analyst", "other-tenant")
    # The platform admin isn't made by hand here. Loading backend.app.main
    # above already created the real demo admin, so the tests use the account
    # that actually ships. Calling the helper again just makes that obvious.
    ensure_demo_admin(db)

    db.commit()
    db.close()
    yield


def login_client(email: str, password: str = PASSWORD) -> TestClient:
    """A test client that's already logged in.

    It keeps the login cookie between requests, so every request after logging
    in is made as that user. Each user gets their own client.
    """
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    # This looks unnecessary, but it catches one confusing problem early. If
    # the cookie is ever set to HTTPS-only, it won't be sent back to the test
    # server: login would seem to work, then every later request would fail.
    # One clear failure here is better than a dozen puzzling ones.
    assert c.get("/api/auth/me").status_code == 200, "cookie was stored but not sent back"
    return c


@pytest.fixture
def anon() -> TestClient:
    return TestClient(app)


@pytest.fixture
def analyst() -> TestClient:
    return login_client(ANALYST_EMAIL)


@pytest.fixture
def tenant_admin() -> TestClient:
    return login_client(TENANT_ADMIN_EMAIL)


@pytest.fixture
def other_analyst() -> TestClient:
    return login_client(OTHER_ANALYST_EMAIL)


@pytest.fixture
def platform_admin() -> TestClient:
    return login_client(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
