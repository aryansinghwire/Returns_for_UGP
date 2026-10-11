"""backend/app/services/dashboard.py - the numbers on the dashboard's front page.

The page has two sections, answering two different questions:

  "Incoming" - orders, over a period you choose. Counted from `orders`.
  "Actions"  - what staff did, over ALL TIME. Counted from `intervention_log`.

The period only applies to the first section. The order dates are made up and
end in November 2021 (see services/dates.py), but actions are recorded with
the real date. One "last 7 days" setting over both would compare two periods
years apart.

Two more rules:

1. Action counts come from the action history, never from order_status.
   order_status only keeps the latest status, so an order that was approved
   and later flagged would only show the flag.

2. Counting orders isn't the same as counting actions. One order can have
   several actions, so the two numbers are kept separate and never added.
"""

from typing import Optional

from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from ..constants import ACTION_TYPES
from ..models import InterventionLog, Order, OrderStatus, Tenant
from .dates import latest_order_date, window_start
from .escalations import count_open_escalated_orders

# Where low, medium and high risk begin. Must match TIER_BREAKS in
# frontend/src/lib/risk.ts, so the website colours a score the same way the
# server counted it. Python and TypeScript can't share a value, so each file
# points at the other - change both together.
RISK_BREAKS = (0.40, 0.70)


def _orders_section(db: Session, tenant: Optional[Tenant], last_n_days: Optional[int]) -> dict:
    """Total orders, how many are low/medium/high risk, and how many are from
    new customers, for the chosen period."""
    # Worked out within the user's own company, so "today" is the newest order
    # *they* can see - the same rule as the order list, so both pages agree.
    reference_date = latest_order_date(db, tenant.id if tenant is not None else None)
    since_date = None
    if last_n_days is not None and reference_date is not None:
        since_date = window_start(reference_date, last_n_days)

    step = case(
        (OrderStatus.current_score < RISK_BREAKS[0], 0),
        (OrderStatus.current_score < RISK_BREAKS[1], 1),
        else_=2,
    ).label("step")
    cold = case(
        ((Order.customer_no_history == 1) | (Order.product_no_history == 1), 1),
        else_=0,
    )

    # The table is named explicitly here, because the query starts with a
    # calculation rather than a column, so SQLAlchemy can't work it out.
    q = (
        db.query(step, func.count(Order.order_id), func.sum(cold))
        .select_from(Order)
        .join(OrderStatus, OrderStatus.order_id == Order.order_id)
        .group_by(step)
    )
    if tenant is not None:
        q = q.filter(Order.tenant_id == tenant.id)
    if since_date is not None:
        # No end date needed: reference_date is already the newest order here,
        # so every order is on or before it.
        q = q.filter(Order.order_date >= since_date)

    # Every band is included, even with no orders, so an empty band shows as
    # zero rather than silently disappearing from the chart.
    counts = [0, 0, 0]
    cold_start = 0
    for index, n, n_cold in q.all():
        counts[int(index)] = int(n or 0)
        cold_start += int(n_cold or 0)

    return {
        "total": sum(counts),
        "risk_mix": {"low": counts[0], "medium": counts[1], "high": counts[2]},
        # Sent as a count, not a percentage: with no orders a percentage would
        # be a division by zero, while a count can just be shown as zero.
        "cold_start": cold_start,
        "last_n_days": last_n_days,
        "reference_date": reference_date,
        "since_date": since_date,
    }


def _actions_section(db: Session, tenant: Optional[Tenant]) -> dict:
    """What staff have done, over all time."""
    # For each action type: how many orders it touched, and how many times it
    # was recorded. Each order is counted once, even if it was flagged both by
    # hand and by a rule. The total number of records comes from the same query.
    touched_q = (
        db.query(
            InterventionLog.action_type,
            func.count(distinct(InterventionLog.order_id)),
            func.count(InterventionLog.id),
        )
        .filter(InterventionLog.event_type == "intervention_action")
        .group_by(InterventionLog.action_type)
    )
    if tenant is not None:
        touched_q = touched_q.filter(InterventionLog.tenant_id == tenant.id)
    touched: dict[str, int] = {}
    total_actions_logged = 0
    for action, n_orders, n_rows in touched_q.all():
        touched[action] = int(n_orders or 0)
        total_actions_logged += int(n_rows or 0)

    # Actions not yet closed, per type. This counts actions, not orders: two
    # reminder emails on one order are two things still waiting.
    open_q = (
        db.query(InterventionLog.action_type, func.count(InterventionLog.id))
        .filter(
            InterventionLog.event_type == "intervention_action",
            InterventionLog.outcome == "pending",
        )
        .group_by(InterventionLog.action_type)
    )
    if tenant is not None:
        open_q = open_q.filter(InterventionLog.tenant_id == tenant.id)
    open_by_type = {action: int(n or 0) for action, n in open_q.all()}

    return {
        "orders_cleared_for_delivery": touched.get("proceed_with_delivery", 0),
        "orders_flagged_for_manual_review": touched.get("flag_for_manual_review", 0),
        "orders_escalated_and_open": count_open_escalated_orders(db, tenant),
        # This includes "approved for delivery" actions too: every action starts
        # as open, and only recording an outcome closes it. That's why the
        # website always shows a note explaining this number.
        "open_actions": sum(open_by_type.values()),
        # Tells "nothing done yet" apart from "things done, but not the kinds
        # shown in the four boxes". A company that has only made phone calls
        # would show four zeros, but its history isn't empty. Zero here really
        # means nothing has ever been recorded, and the page says so in words.
        "total_actions_logged": total_actions_logged,
        "open_by_action_type": [
            {"action_type": action, "open_actions": open_by_type.get(action, 0)}
            for action in sorted(ACTION_TYPES)
        ],
    }


def get_dashboard(db: Session, tenant: Optional[Tenant], last_n_days: Optional[int] = None) -> dict:
    """tenant=None means the platform admin, who sees every company - the same
    as everywhere else in the app."""
    return {
        "orders": _orders_section(db, tenant, last_n_days),
        "actions": _actions_section(db, tenant),
    }
