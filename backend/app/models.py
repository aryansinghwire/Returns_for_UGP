"""backend/app/models.py - the database tables.

There are seven tables:

  tenants            the companies (made up for the demo)
  users              login accounts, with each user's role and company
  orders             NEVER CHANGES - exactly what the model saw and scored
  order_status       CHANGES - where each order stands right now (one row each)
  intervention_log   ONLY ADDED TO - what people did, and when
  automated_rules    each company's automatic rules
  baseline_stats     each group's normal return rate, worked out once on load

The three order tables are kept separate on purpose. Merging them would lose
the history of what happened.

WARNING: ADDING A COLUMN HERE WON'T UPDATE AN EXISTING DATABASE. There's no
upgrade system. On startup the server creates any missing *tables*, but it
never adds missing *columns* - so a new column silently isn't there, and
anything that uses it fails. To add one, start a fresh database
(`./run_dev.sh --reset-db`) or add the column by hand. See main.py for the one
automatic repair, and the note under User below for why it mustn't be copied.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, Column, Integer, String, Float, Text, DateTime, ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class User(Base):
    """A login account. The user's role and company are stored here, so the
    server can check them rather than trusting what the user says.

    tenant_id is empty only for the platform admin, who works across every
    company. Everyone else must belong to one company.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Saved in lower case with spaces trimmed (see routers/auth.py). SQLite
    # treats capitals as different letters, so without this, alice@x.com and
    # Alice@X.com could be two separate accounts.
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(String, nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # 1 = active, 0 = disabled. Disabling keeps the account (and its history)
    # instead of deleting it. A number rather than true/false, to match
    # AutomatedRule.is_active below.
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=utcnow)
    last_login_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant")

    __table_args__ = (
        # The rule deps.py depends on: the platform admin has no company, and
        # everyone else has exactly one. The database itself enforces it, so no
        # code can forget to.
        #
        # Changing this rule now would mean rebuilding the users table, which
        # holds the only copy of everyone's account. So never copy the
        # _drop_stale_rules_table trick from main.py onto it.
        CheckConstraint(
            "(role = 'admin' AND tenant_id IS NULL) "
            "OR (role <> 'admin' AND tenant_id IS NOT NULL)",
            name="ck_users_role_tenant",
        ),
    )


class Order(Base):
    """One scored order, loaded once from serving/output/orders_seed.json and
    never changed. If someone overrides a score, the new one goes in
    OrderStatus - so the model's original score can always be checked."""
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    customer_ref = Column(String, nullable=False)
    product_ref = Column(String, nullable=False)
    order_date = Column(String, nullable=False, index=True)  # e.g. 2021-10-14; made up

    model_risk_score = Column(Float, nullable=False, index=True)
    reasons_json = Column(Text, nullable=False)

    customer_no_history = Column(Integer, nullable=False)
    product_no_history = Column(Integer, nullable=False)
    customer_return_rate = Column(Float, nullable=False)
    product_return_rate = Column(Float, nullable=False)
    avg_discount_value = Column(Float, nullable=False)
    avg_gbp_price = Column(Float, nullable=False)

    country_bucket = Column(String, nullable=False)
    # Not called "brand" on purpose. This is a real product detail, and must
    # never be confused with the made-up companies (tenants).
    product_brand_bucket = Column(String, nullable=False)
    product_type_bucket = Column(String, nullable=False)

    raw_features_json = Column(Text, nullable=False)

    # Whether it was really returned. Never shown for a single order - only
    # as group totals in alerts and reports.
    is_returned_ground_truth = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=utcnow)

    tenant = relationship("Tenant")
    status = relationship("OrderStatus", uselist=False, back_populates="order")


class OrderStatus(Base):
    """Where one order stands right now. Exactly one row per order."""
    __tablename__ = "order_status"

    order_id = Column(String, ForeignKey("orders.order_id"), primary_key=True)
    current_score = Column(Float, nullable=False)
    # Allowed values are in constants.ORDER_STATUSES. Several parts of the app
    # update this, and each update replaces the last - so it only shows the
    # latest thing that happened. For the full history, read intervention_log.
    status = Column(String, nullable=False, default="pending")

    override_score = Column(Float, nullable=True)
    override_reason = Column(Text, nullable=True)
    overridden_by = Column(String, nullable=True)
    overridden_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    order = relationship("Order", back_populates="status")


class InterventionLog(Base):
    """The history of everything people did. Rows are only ever added, never
    changed or deleted. Score overrides, actions, their outcomes and the
    admin's audit log all come from this one table."""
    __tablename__ = "intervention_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.order_id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # These four columns hold saved names. Rows here are never deleted, so
    # renaming a value would leave every old row pointing at something that no
    # longer exists. To change how one looks on screen, change its label in the
    # frontend's ACTION_LABELS instead. Allowed values: action_type is in
    # constants.ACTION_TYPES, outcome in constants.OUTCOMES; event_type and
    # trigger are checked in routers/audit.py and routers/orders.py.
    event_type = Column(String, nullable=False)        # override | intervention_action
    action_type = Column(String, nullable=True)
    trigger = Column(String, nullable=False, default="manual")  # manual | automated_threshold
    outcome = Column(String, nullable=True)

    old_score = Column(Float, nullable=True)
    new_score = Column(Float, nullable=True)
    note = Column(Text, nullable=True)

    actor_role = Column(String, nullable=False)
    actor_name = Column(String, nullable=True)

    created_at = Column(DateTime, default=utcnow, index=True)

    tenant = relationship("Tenant")


class AutomatedRule(Base):
    """An automatic rule: "for orders scoring between score_min and
    score_max, do this action."

    Using a range rather than just a minimum lets a company send medium-risk
    orders to a cheap action (a reminder email) and high-risk ones to an
    expensive action (a phone call), without the two overlapping.

    Each rule belongs to one company, and a company's admin can only change
    their own - see deps.require_tenant_scope.
    """
    __tablename__ = "automated_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    score_min = Column(Float, nullable=False)
    score_max = Column(Float, nullable=False)
    action_type = Column(String, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=utcnow)

    tenant = relationship("Tenant")


class BaselineStat(Base):
    """Each group's normal return rate, worked out once by scripts/seed_db.py.
    Alerts compare recent orders against these."""
    __tablename__ = "baseline_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    cohort_type = Column(String, nullable=False)  # overall | product | country | product_type
    cohort_key = Column(String, nullable=False)
    baseline_return_rate = Column(Float, nullable=False)
    n_baseline_orders = Column(Integer, nullable=False)
    computed_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "cohort_type", "cohort_key", name="uq_baseline_cohort"),
    )
