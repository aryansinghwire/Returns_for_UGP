"""backend/app/config.py - settings for the server: file paths, login, roles
and alert thresholds."""

import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "orders.db")
# Can be changed so the tests use a throwaway database, not the real one.
DB_URL = os.environ.get("RETURNS_DASHBOARD_DB_URL", f"sqlite:///{DB_PATH}")

REPO_ROOT = os.path.dirname(BACKEND_DIR)
SEED_JSON_PATH = os.path.join(REPO_ROOT, "serving", "output", "orders_seed.json")

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# The roles, from least to most powerful. Each role can do everything the
# ones below it can. "tenant_admin" manages one company; "admin" is the
# platform admin, who can see every company.
#
# ADDING A ROLE MEANS CHANGING MORE THAN THIS LIST. Role names also appear in
# constants.ROLES (the display name), SIGNUP_ROLES below (if people can pick
# it), the ck_users_role_tenant rule in models.py (if it works differently with
# companies), and frontend/src/api/types.ts. Nothing checks they match.
#
# Forgetting this list is easy to spot: the server refuses every request from
# that role. Forgetting constants.ROLES is easy to miss: everything works, but
# the account menu shows a blank instead of the role's name.
ROLE_LEVELS = {
    "ops_analyst": 1,
    "tenant_admin": 2,
    "admin": 3,
}

# There is deliberately no default role. A request from someone who isn't
# logged in is refused - it is never quietly given the lowest role.

# --- login -------------------------------------------------------------------
# The secret key that signs login tokens. If it isn't set, a fixed default is
# used - and that default is public, so anyone with this code could create a
# valid admin login. That's only acceptable because this is a demo. Anywhere
# real must set RETURNS_DASHBOARD_JWT_SECRET, and remove the demo admin in
# bootstrap.py.
#
# The default is fixed rather than random because the dev server restarts on
# every code change, and a new random key each time would log you out.
JWT_SECRET = os.environ.get(
    "RETURNS_DASHBOARD_JWT_SECRET",
    "returns-dashboard-development-signing-key-not-a-secret",
)
JWT_SECRET_IS_DEFAULT = "RETURNS_DASHBOARD_JWT_SECRET" not in os.environ
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 8 * 60 * 60  # one working day; then you log in again

SESSION_COOKIE_NAME = "returns_session"
# A "Secure" cookie is only sent over HTTPS. Turned on over plain http, login
# would seem to work but every request after it would fail. Development and
# the tests use plain http, so this is off unless you turn it on.
SESSION_COOKIE_SECURE = os.environ.get("RETURNS_DASHBOARD_COOKIE_SECURE", "0") == "1"

# Roles people can choose when signing up. "admin" is left out on purpose:
# letting anyone make themselves the platform admin would be a security hole.
SIGNUP_ROLES = ("ops_analyst", "tenant_admin")

# --- alerts (see services/alerts.py) -----------------------------------------
# All four alert settings are kept together here.
#
# A group of orders triggers an alert when its recent return rate is higher
# than usual by at least ALERT_MIN_GAP, across at least ALERT_MIN_N orders. The
# minimum matters: there are only about 397 products in the test data, and
# without it small groups would trigger alerts constantly by chance.
ALERT_MIN_GAP = 0.15
ALERT_MIN_N = 15
# How big the gap must be for an alert to be 'high' rather than 'medium'.
ALERT_HIGH_GAP = 0.25
# How many recent days to look at. Counted back from the newest order in the
# data, not from today, because the dates are made up - see services/dates.py.
ALERT_WINDOW_DAYS = 14
