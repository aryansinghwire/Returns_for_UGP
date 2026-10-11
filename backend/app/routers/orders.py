"""backend/app/routers/orders.py - everything about orders: the filtered list,
one order's details, overriding a score, logging an action and its outcome,
and an order's history."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session

from ..constants import ACTION_TYPES, CLOSING_OUTCOMES, ORDER_STATUSES, OUTCOMES
from ..deps import (
    get_current_user, get_db, get_role, get_scoped_tenant_or_none, require_role,
)
from ..models import InterventionLog, Order, OrderStatus, Tenant, User
from ..schemas import (
    ActionOutcomeUpdate, ActionRequest, HistoryEntry, OrderDetail, OrderListItem,
    OverrideRequest, PaginatedOrders, ScoreHistogram, ScoreHistogramBucket,
)
from ..services.dates import MAX_PERIOD_DAYS, latest_order_date, window_start
from ..services.queue import order_detail, order_list_item

router = APIRouter(prefix="/orders", tags=["orders"])

SORT_OPTIONS = {"score", "-score", "date", "-date"}

# How many bars the risk chart above the order list has. Twenty bars, each
# covering 0.05 of the score range, is enough detail to read at a glance.
SCORE_BUCKETS = 20


def _get_order_and_status(db: Session, order_id: str, tenant: Optional[Tenant]):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"order '{order_id}' not found")
    if tenant is not None and order.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail=f"order '{order_id}' not found for tenant '{tenant.slug}'")
    status = order.status
    if status is None:
        raise HTTPException(status_code=500, detail=f"order '{order_id}' has no status row - seed data issue")
    return order, status


def _filtered_orders(
    db: Session,
    tenant: Optional[Tenant],
    *,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    country: Optional[str] = None,
    product_type: Optional[str] = None,
    cold_start: Optional[bool] = None,
    last_n_days: Optional[int] = None,
):
    """The order list's filters, written once and used in two places.

    The list and the risk chart above it must filter orders the same way, or
    the chart would describe different orders from the list beneath it. Also
    returns the date range used, so the website can say which dates it's
    showing.
    """
    q = db.query(Order, OrderStatus).join(OrderStatus, OrderStatus.order_id == Order.order_id)

    if tenant is not None:
        q = q.filter(Order.tenant_id == tenant.id)

    # Worked out within the user's own company, so "the last N days" counts
    # back from the newest order *they* can see.
    reference_date = latest_order_date(db, tenant.id if tenant is not None else None)
    since_date = None
    if last_n_days is not None and reference_date is not None:
        since_date = window_start(reference_date, last_n_days)
        # No end date needed: reference_date is already the newest order here,
        # so every order is on or before it.
        q = q.filter(Order.order_date >= since_date)

    if status is not None:
        q = q.filter(OrderStatus.status == status)
    if min_score is not None:
        q = q.filter(OrderStatus.current_score >= min_score)
    if max_score is not None:
        q = q.filter(OrderStatus.current_score <= max_score)
    if country is not None:
        q = q.filter(Order.country_bucket == country)
    if product_type is not None:
        q = q.filter(Order.product_type_bucket == product_type)
    if cold_start is True:
        q = q.filter((Order.customer_no_history == 1) | (Order.product_no_history == 1))
    elif cold_start is False:
        q = q.filter(Order.customer_no_history == 0, Order.product_no_history == 0)

    return q, reference_date, since_date


@router.get("", response_model=PaginatedOrders)
def list_orders(
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    status: Optional[str] = Query(default=None),
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    max_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    country: Optional[str] = Query(default=None),
    product_type: Optional[str] = Query(default=None),
    cold_start: Optional[bool] = Query(default=None),
    last_n_days: Optional[int] = Query(
        default=None, ge=1, le=MAX_PERIOD_DAYS,
        description=("keep only orders in the trailing N-day window ending at the "
                     "latest order date in scope (this dataset's dates are synthetic "
                     "and end in Nov 2021, so wall-clock today would match nothing)"),
    ),
    sort: str = Query(default="-score"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    if sort not in SORT_OPTIONS:
        raise HTTPException(status_code=422, detail=f"sort must be one of {sorted(SORT_OPTIONS)}")
    if status is not None and status not in ORDER_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(ORDER_STATUSES)}")

    q, reference_date, since_date = _filtered_orders(
        db, tenant, status=status, min_score=min_score, max_score=max_score,
        country=country, product_type=product_type, cold_start=cold_start,
        last_n_days=last_n_days,
    )

    total = q.count()

    order_col = OrderStatus.current_score if sort.endswith("score") else Order.order_date
    order_clause = order_col.desc() if sort.startswith("-") else order_col.asc()
    q = q.order_by(order_clause)

    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [OrderListItem(**order_list_item(o, s)) for o, s in rows]

    return PaginatedOrders(
        items=items, page=page, page_size=page_size, total=total,
        reference_date=reference_date, since_date=since_date,
    )


@router.get("/score-histogram", response_model=ScoreHistogram)
def score_histogram(
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    status: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    product_type: Optional[str] = Query(default=None),
    cold_start: Optional[bool] = Query(default=None),
    last_n_days: Optional[int] = Query(default=None, ge=1, le=MAX_PERIOD_DAYS),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    """How many orders fall in each score band, for the chart above the list.

    Uses every filter except the score range, because the user picks that
    range on this chart - it has to keep showing the orders outside it too.

    Must stay above the /{order_id} route. The server checks routes in order,
    and otherwise it would read "score-histogram" as an order number.
    """
    if status is not None and status not in ORDER_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(ORDER_STATUSES)}")

    q, reference_date, since_date = _filtered_orders(
        db, tenant, status=status, country=country, product_type=product_type,
        cold_start=cold_start, last_n_days=last_n_days,
    )

    bucket = cast(OrderStatus.current_score * SCORE_BUCKETS, Integer).label("bucket")
    rows = q.with_entities(bucket, func.count()).group_by(bucket).all()

    counts = [0] * SCORE_BUCKETS
    for index, count in rows:
        # A score of exactly 1.0 would land one past the last bar. Put it in
        # the top bar instead.
        counts[min(int(index), SCORE_BUCKETS - 1)] += count

    width = 1.0 / SCORE_BUCKETS
    return ScoreHistogram(
        buckets=[
            ScoreHistogramBucket(lower=i * width, upper=(i + 1) * width, count=c)
            for i, c in enumerate(counts)
        ],
        total=sum(counts),
        reference_date=reference_date,
        since_date=since_date,
    )


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: str,
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    order, status = _get_order_and_status(db, order_id, tenant)
    return OrderDetail(**order_detail(order, status))


@router.post("/{order_id}/override", response_model=OrderDetail)
def override_order(
    order_id: str,
    body: OverrideRequest,
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("ops_analyst")),
    user: User = Depends(get_current_user),
):
    if not (0.0 <= body.new_score <= 1.0):
        raise HTTPException(status_code=422, detail="new_score must be between 0 and 1")

    order, status = _get_order_and_status(db, order_id, tenant)
    old_score = status.current_score

    status.override_score = body.new_score
    status.override_reason = body.reason
    # Who did this comes from the login, never from what the request says.
    # Otherwise anyone could record an action under someone else's name, in a
    # history that can never be corrected.
    status.overridden_by = user.display_name
    status.overridden_at = datetime.now(timezone.utc)
    status.current_score = body.new_score
    status.status = "overridden"

    db.add(InterventionLog(
        order_id=order_id,
        tenant_id=order.tenant_id,
        event_type="override",
        trigger="manual",
        old_score=old_score,
        new_score=body.new_score,
        note=body.reason,
        actor_role=user.role,
        actor_name=user.display_name,
    ))
    db.commit()
    db.refresh(order)
    db.refresh(status)
    return OrderDetail(**order_detail(order, status))


@router.post("/{order_id}/actions", response_model=HistoryEntry, status_code=201)
def create_action(
    order_id: str,
    body: ActionRequest,
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("ops_analyst")),
    user: User = Depends(get_current_user),
):
    if body.action_type not in ACTION_TYPES:
        raise HTTPException(status_code=422, detail=f"action_type must be one of {sorted(ACTION_TYPES)}")
    if body.trigger not in ("manual", "automated_threshold"):
        raise HTTPException(status_code=422, detail="trigger must be 'manual' or 'automated_threshold'")

    order, status = _get_order_and_status(db, order_id, tenant)

    log = InterventionLog(
        order_id=order_id,
        tenant_id=order.tenant_id,
        event_type="intervention_action",
        action_type=body.action_type,
        trigger=body.trigger,
        outcome="pending",
        note=body.note,
        actor_role=user.role,
        actor_name=user.display_name,
    )
    db.add(log)
    status.status = "actioned"
    db.commit()
    db.refresh(log)
    return log


@router.patch("/{order_id}/actions/{log_id}", response_model=HistoryEntry)
def update_action_outcome(
    order_id: str,
    log_id: int,
    body: ActionOutcomeUpdate,
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("ops_analyst")),
    user: User = Depends(get_current_user),
):
    if body.outcome not in OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(OUTCOMES)}")

    order, status = _get_order_and_status(db, order_id, tenant)
    log = (
        db.query(InterventionLog)
        .filter(
            InterventionLog.id == log_id,
            InterventionLog.order_id == order_id,
            InterventionLog.event_type == "intervention_action",
        )
        .first()
    )
    if log is None:
        raise HTTPException(status_code=404, detail=f"action log '{log_id}' not found for order '{order_id}'")

    log.outcome = body.outcome
    if body.note is not None:
        log.note = body.note
    if body.outcome in CLOSING_OUTCOMES:
        status.status = "closed"

    db.commit()
    db.refresh(log)
    return log


@router.get("/{order_id}/history", response_model=list[HistoryEntry])
def get_order_history(
    order_id: str,
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    _get_order_and_status(db, order_id, tenant)
    logs = (
        db.query(InterventionLog)
        .filter(InterventionLog.order_id == order_id)
        .order_by(InterventionLog.created_at.asc())
        .all()
    )
    return logs
