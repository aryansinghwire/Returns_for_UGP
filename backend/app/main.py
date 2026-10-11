"""backend/app/main.py - puts the server together and starts it.

Run from the main project folder:
    .venv/bin/uvicorn backend.app.main:app --reload --port 8000

Usually you'd use ./run_dev.sh instead, which also starts the website.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from .bootstrap import ensure_demo_admin
from .config import CORS_ORIGINS
from .db import Base, SessionLocal, engine
from .routers import (
    alerts, audit, auth, dashboard, escalations, meta, orders, reporting, rules,
    tenants,
)


def _drop_stale_rules_table() -> None:
    """Fix a database made by an older version of the app.

    Rules used to have a single minimum score; now they have a range. A
    database from before that change still has the old column, and every rule
    lookup would fail. There's no upgrade system, so this deletes and recreates
    just the rules table.

    That's safe only because rules are quick to type in again. Orders, score
    overrides and the history are untouched. Only saved rules are lost, once.
    """
    inspector = inspect(engine)
    if "automated_rules" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("automated_rules")}
    if "score_threshold" in columns:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE automated_rules"))


def _ensure_demo_admin_exists() -> None:
    """Make sure the demo admin account exists.

    A database made before logins were added has orders but no users. And
    run_dev.sh doesn't reload the database if one already exists. Without this,
    you'd get a login page and no account that could sign in.

    It runs as soon as this file loads, not in a startup hook. That's on
    purpose: the test tools don't run startup hooks the way the tests use them,
    so a startup hook would be skipped during testing - and the tests would be
    checking a different setup from the real one.
    """
    db = SessionLocal()
    try:
        ensure_demo_admin(db)
        db.commit()
    finally:
        db.close()


_drop_stale_rules_table()
# Creates any tables that don't exist yet. It does NOT add new columns to
# tables that already exist - see the warning at the top of models.py.
Base.metadata.create_all(bind=engine)
_ensure_demo_admin_exists()

app = FastAPI(title="Pre-Dispatch Returns Risk Engine - Ops Dashboard Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_prototype_marker(request, call_next):
    """Tag every response "X-Prototype: true", so any program reading the
    data can tell it's from a demo, not a real system. The full notice for
    people is at /api/meta."""
    response = await call_next(request)
    response.headers["X-Prototype"] = "true"
    return response


app.include_router(auth.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
app.include_router(tenants.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(reporting.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(escalations.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
