"""backend/app/schemas.py - the shape of the data the server accepts and sends
back. frontend/src/api/types.ts has a matching copy - keep the two in step."""

import re
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .config import SIGNUP_ROLES
from .passwords import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH

# A simple, loose email check, on purpose. Pydantic's built-in email type needs
# an extra package that looks up the domain on the internet during each
# request - and if that package is missing, the whole server fails to start.
# The only real test of an email address is whether mail arrives, and this app
# never sends any.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _normalize_email(value: str) -> str:
    return value.strip().lower()


class SignupRequest(BaseModel):
    """Signing up to an EXISTING company.

    `role` may only be one of config.SIGNUP_ROLES. Asking for "admin" is
    refused automatically, so nobody can forget to check it.

    Letting people choose between analyst and company admin is a demo
    convenience - a real product would use invitations.
    """
    tenant_slug: str
    email: str
    password: str
    role: Literal[SIGNUP_ROLES]  # type: ignore[valid-type]
    display_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        v = _normalize_email(v)
        if not EMAIL_RE.match(v):
            raise ValueError("not a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
        if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        # Only tidy it up - don't check the format here. A failed login must
        # never reveal *why* it failed.
        return _normalize_email(v)


class MeOut(BaseModel):
    """The logged-in user, as the website needs it. Contains nothing secret -
    no password, no token. The login itself is kept in a cookie the website
    can't read."""
    id: int
    email: str
    display_name: str
    role: str
    role_label: str
    tenant_slug: Optional[str] = None  # None means the platform admin
    tenant_name: Optional[str] = None


class DemoCredentialsOut(BaseModel):
    """The demo login details, sent to the login page. Sending them from here
    means the page always shows the account the server actually creates -
    a second copy in the website could fall out of date."""
    email: str
    password: str
    notice: str


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class TenantCreate(BaseModel):
    name: str


class OrderListItem(BaseModel):
    """One row of the order list. Leaves out the full feature data, to keep the
    list fast to load."""
    order_id: str
    tenant: str
    order_date: str
    customer_ref: str
    product_ref: str
    current_score: float
    model_risk_score: float
    status: str
    reasons: list[str]
    customer_no_history: bool
    product_no_history: bool
    country_bucket: str
    product_brand_bucket: str
    product_type_bucket: str


class PaginatedOrders(BaseModel):
    items: list[OrderListItem]
    page: int
    page_size: int
    total: int
    # The dates are made up and end in November 2021, so "today" means the
    # newest order in the data, not the real date (see services/dates.py).
    # Both dates are sent back so the website can show exactly which period
    # it's displaying, rather than looking live.
    reference_date: Optional[str] = None
    since_date: Optional[str] = None


class ScoreHistogramBucket(BaseModel):
    """One bar of the risk chart above the order list."""
    lower: float
    upper: float
    count: int


class ScoreHistogram(BaseModel):
    """How risk is spread across the order list. It uses every filter except
    the score range, because the chart shows the whole spread and the score
    range is what the user picks *on* it. Limiting the chart to that range
    would make the selection look like it covered everything."""
    buckets: list[ScoreHistogramBucket]
    total: int
    reference_date: Optional[str] = None
    since_date: Optional[str] = None


class OrderDetail(OrderListItem):
    """Everything about one order. Deliberately leaves out whether it was
    really returned - that must never be shown for a single order."""
    customer_return_rate: float
    product_return_rate: float
    avg_discount_value: float
    avg_gbp_price: float
    override_score: Optional[float] = None
    override_reason: Optional[str] = None
    overridden_by: Optional[str] = None
    overridden_at: Optional[datetime] = None
    raw_features: dict[str, Any]


class OverrideRequest(BaseModel):
    """A score override. There's no field for who did it - the server takes
    that from the login, so nobody can record an action under someone else's
    name. Unexpected fields are simply ignored, so an older version of the
    website that still sends one won't get an error."""
    new_score: float
    reason: str


class ActionRequest(BaseModel):
    """An action on an order. No "who did it" field - see OverrideRequest."""
    action_type: str
    trigger: str = "manual"
    note: Optional[str] = None


class ActionOutcomeUpdate(BaseModel):
    outcome: str
    note: Optional[str] = None


class HistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    action_type: Optional[str] = None
    trigger: str
    outcome: Optional[str] = None
    old_score: Optional[float] = None
    new_score: Optional[float] = None
    note: Optional[str] = None
    actor_role: str
    actor_name: Optional[str] = None
    created_at: datetime


class AuditLogEntry(HistoryEntry):
    order_id: str
    tenant: str


class PaginatedAuditLog(BaseModel):
    items: list[AuditLogEntry]
    page: int
    page_size: int
    total: int


class ReportingBucket(BaseModel):
    bucket: str
    baseline_return_rate: float
    actual_return_rate: float
    n_orders: int


class ReportingResponse(BaseModel):
    cohort_type: str
    cohort_key: str
    granularity: str
    buckets: list[ReportingBucket]


class EscalationOut(BaseModel):
    """One escalated order, as shown in the company admin's list.

    Includes log_id as well as order_id, because an order can be escalated
    more than once - and closing one means recording an outcome against that
    particular escalation.
    """
    log_id: int
    order_id: str
    tenant: str
    order_date: str
    current_score: float
    model_risk_score: float
    order_status: str
    raised_by: Optional[str] = None
    raised_by_role: str
    raised_at: datetime
    trigger: str
    note: Optional[str] = None
    outcome: Optional[str] = None


class AlertOut(BaseModel):
    tenant: str
    cohort_type: str
    cohort_key: str
    baseline_rate: float
    actual_rate: float
    gap: float
    n_orders: int
    severity: str


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant: str
    tenant_slug: str
    name: str
    score_min: float
    score_max: float
    action_type: str
    is_active: bool


class RuleCreate(BaseModel):
    name: str
    score_min: float
    score_max: float
    action_type: str


class RuleUpdate(BaseModel):
    is_active: Optional[bool] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    action_type: Optional[str] = None


class MetaOut(BaseModel):
    generated_at: str
    model: str
    n_orders: int
    achieved_overall_auc: Optional[float]
    achieved_cold_customer_auc: Optional[float]
    tenants: list[str]
    notice: str


class DashboardRiskMix(BaseModel):
    """How many orders are low (under 0.40), medium (under 0.70) and high risk.
    Uses the same cut-offs as frontend/src/lib/risk.ts, so a band's colour and
    its count always agree."""
    low: int
    medium: int
    high: int


class DashboardOrders(BaseModel):
    """The dashboard's "Incoming" section: orders over the chosen period.

    The dates sit here, not on the whole response, because they only apply to
    this section. The "Actions" section covers all time.

    reference_date is empty for a company with no orders yet. That's normal for
    a brand-new company, not an error.
    """
    total: int
    risk_mix: DashboardRiskMix
    cold_start: int
    last_n_days: Optional[int] = None
    reference_date: Optional[str] = None
    since_date: Optional[str] = None


class DashboardOpenAction(BaseModel):
    action_type: str
    open_actions: int


class DashboardActions(BaseModel):
    """The dashboard's "Actions" section: what staff have done. Covers ALL
    TIME - there's no date filter.

    That's because the order dates are made up and end in 2021, while actions
    are recorded with the real date. One date filter over both would compare
    two periods years apart under one label.

    The first three numbers count ORDERS. open_actions counts ACTIONS. One
    order can have several actions, so the two kinds of number are never added
    together.

    total_actions_logged is worked out on the server so the website can tell
    "nothing done yet" from "things done, but not the kinds shown here" - a
    company that has only made phone calls would otherwise look empty.

    These numbers come from the action history, not from order_status, which
    only keeps the latest status and would lose earlier actions.
    """
    orders_cleared_for_delivery: int
    orders_flagged_for_manual_review: int
    orders_escalated_and_open: int
    open_actions: int
    total_actions_logged: int
    open_by_action_type: list[DashboardOpenAction]


class DashboardOut(BaseModel):
    orders: DashboardOrders
    actions: DashboardActions
