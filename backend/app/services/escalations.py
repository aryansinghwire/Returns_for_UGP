"""backend/app/services/escalations.py - the company admin's list of escalated
orders.

There's no separate escalations table, on purpose. Escalating is just another
action, and every action is already recorded in intervention_log - so this
reads from there. A second table would have to be kept in step with it, and
the two could end up disagreeing.

An escalation is open until someone records how it was dealt with. That
happens the same way as for any other action:
PATCH /api/orders/{id}/actions/{log_id}.
"""

from typing import Optional

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from ..models import InterventionLog, Order, OrderStatus, Tenant

# What counts as "an escalation" and "still open", defined once. The
# dashboard's escalation count uses these too, so it always matches this list.
ESCALATION_ACTION = (
    InterventionLog.event_type == "intervention_action",
    InterventionLog.action_type == "escalate",
)
OPEN_OUTCOME = InterventionLog.outcome == "pending"


def list_escalations(
    db: Session,
    tenant: Optional[Tenant],
    include_resolved: bool = False,
) -> list[dict]:
    """Escalated orders, newest first.

    tenant=None means the platform admin, so every company is included - the
    same as everywhere else in the app.
    """
    q = (
        db.query(InterventionLog, Order, OrderStatus)
        .join(Order, Order.order_id == InterventionLog.order_id)
        .join(OrderStatus, OrderStatus.order_id == Order.order_id)
        .filter(*ESCALATION_ACTION)
    )
    if tenant is not None:
        q = q.filter(InterventionLog.tenant_id == tenant.id)
    if not include_resolved:
        q = q.filter(OPEN_OUTCOME)

    rows = q.order_by(InterventionLog.created_at.desc()).all()

    return [
        {
            # The action's own ID, not the order's - closing an escalation means
            # recording an outcome against this particular one.
            "log_id": log.id,
            "order_id": order.order_id,
            "tenant": order.tenant.name,
            "order_date": order.order_date,
            "current_score": status.current_score,
            "model_risk_score": order.model_risk_score,
            "order_status": status.status,
            "raised_by": log.actor_name,
            "raised_by_role": log.actor_role,
            "raised_at": log.created_at,
            "trigger": log.trigger,
            "note": log.note,
            "outcome": log.outcome,
        }
        for log, order, status in rows
    ]


def count_open_escalated_orders(db: Session, tenant: Optional[Tenant]) -> int:
    """How many orders are escalated and not yet dealt with.

    Counts each order once, even if it's been escalated several times (raised,
    closed, then raised again). That's why the list uses each escalation's own
    ID, but this count doesn't.
    """
    q = db.query(func.count(distinct(InterventionLog.order_id))).filter(
        *ESCALATION_ACTION, OPEN_OUTCOME
    )
    if tenant is not None:
        q = q.filter(InterventionLog.tenant_id == tenant.id)
    return int(q.scalar() or 0)
