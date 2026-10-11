"""backend/app/services/rules_engine.py - runs a company's automatic rules
against its orders.

Rules only run when someone presses the button (POST /api/rules/evaluate).
Running them on a schedule would need a background job system, which is more
than a demo needs. That's a choice, not something forgotten.
"""

from sqlalchemy.orm import Session

from ..models import AutomatedRule, InterventionLog, Order, OrderStatus


def evaluate_rules(db: Session, tenant_id: int) -> dict:
    rules = (
        db.query(AutomatedRule)
        .filter(AutomatedRule.tenant_id == tenant_id, AutomatedRule.is_active == 1)
        .all()
    )
    actions_created = 0
    details = []

    for rule in rules:
        candidates = (
            db.query(Order, OrderStatus)
            .join(OrderStatus, OrderStatus.order_id == Order.order_id)
            .filter(
                Order.tenant_id == tenant_id,
                OrderStatus.status == "pending",
                OrderStatus.current_score >= rule.score_min,
                OrderStatus.current_score <= rule.score_max,
            )
            .all()
        )

        fired_for_rule = 0
        for order, status in candidates:
            already_fired = (
                db.query(InterventionLog)
                .filter(
                    InterventionLog.order_id == order.order_id,
                    InterventionLog.trigger == "automated_threshold",
                    InterventionLog.action_type == rule.action_type,
                )
                .first()
            )
            if already_fired is not None:
                continue

            db.add(InterventionLog(
                order_id=order.order_id,
                tenant_id=tenant_id,
                event_type="intervention_action",
                action_type=rule.action_type,
                trigger="automated_threshold",
                outcome="pending",
                note=(f"Automated: rule '{rule.name}' fired "
                      f"(score {status.current_score:.3f} is inside the configured "
                      f"window {rule.score_min:.2f}-{rule.score_max:.2f})"),
                actor_role="admin",
                actor_name="system (automated rule)",
            ))
            status.status = "actioned"
            fired_for_rule += 1
            actions_created += 1

        details.append({"rule": rule.name, "actions_created": fired_for_rule})

    db.commit()
    return {"rules_evaluated": len(rules), "actions_created": actions_created, "details": details}
