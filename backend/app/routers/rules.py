"""backend/app/routers/rules.py - creating, listing and changing automatic
rules, and running them.

Each company has its own rules. A company admin can only see or change their
own company's. Only the platform admin can see every company's rules.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..constants import RULE_ACTION_TYPES
from ..deps import (
    get_actor_tenant, get_db, get_role, get_scoped_tenant_or_none, require_role,
    require_tenant_scope,
)
from ..models import AutomatedRule, Tenant
from ..schemas import RuleCreate, RuleOut, RuleUpdate
from ..services.rules_engine import evaluate_rules

router = APIRouter(prefix="/rules", tags=["rules"])


def _to_rule_out(rule: AutomatedRule) -> dict:
    return {
        "id": rule.id,
        "tenant": rule.tenant.name,
        "tenant_slug": rule.tenant.slug,
        "name": rule.name,
        "score_min": rule.score_min,
        "score_max": rule.score_max,
        "action_type": rule.action_type,
        "is_active": bool(rule.is_active),
    }


def _validate_window(score_min: float, score_max: float) -> None:
    for label, value in (("score_min", score_min), ("score_max", score_max)):
        if not (0.0 <= value <= 1.0):
            raise HTTPException(status_code=422, detail=f"{label} must be between 0 and 1")
    if score_min > score_max:
        raise HTTPException(status_code=422, detail="score_min must be <= score_max")


@router.get("", response_model=list[RuleOut])
def list_rules(
    tenant: Optional[Tenant] = Depends(get_scoped_tenant_or_none),
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
):
    # Everyone except the platform admin has already been limited to their own
    # company, so `tenant` is only empty for the platform admin.
    q = db.query(AutomatedRule)
    if tenant is not None:
        q = q.filter(AutomatedRule.tenant_id == tenant.id)
    return [RuleOut(**_to_rule_out(r)) for r in q.all()]


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(
    body: RuleCreate,
    tenant: Tenant = Depends(require_tenant_scope),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("tenant_admin")),
):
    if body.action_type not in RULE_ACTION_TYPES:
        raise HTTPException(status_code=422, detail=f"action_type must be one of {sorted(RULE_ACTION_TYPES)}")
    _validate_window(body.score_min, body.score_max)

    rule = AutomatedRule(
        tenant_id=tenant.id,
        name=body.name,
        score_min=body.score_min,
        score_max=body.score_max,
        action_type=body.action_type,
        is_active=1,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RuleOut(**_to_rule_out(rule))


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: int,
    body: RuleUpdate,
    db: Session = Depends(get_db),
    role: str = Depends(require_role("tenant_admin")),
    actor_tenant: Optional[str] = Depends(get_actor_tenant),
):
    rule = db.query(AutomatedRule).filter(AutomatedRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail=f"rule '{rule_id}' not found")

    # The rule already belongs to a company, so check the user against the
    # rule's own company - not against whatever company the request names.
    if role != "admin" and actor_tenant != rule.tenant.slug:
        raise HTTPException(
            status_code=403,
            detail=(f"role '{role}' is scoped to tenant '{actor_tenant}' and cannot "
                    f"change a rule owned by '{rule.tenant.slug}'"),
        )

    if body.action_type is not None:
        if body.action_type not in RULE_ACTION_TYPES:
            raise HTTPException(status_code=422, detail=f"action_type must be one of {sorted(RULE_ACTION_TYPES)}")
        rule.action_type = body.action_type
    if body.score_min is not None or body.score_max is not None:
        new_min = body.score_min if body.score_min is not None else rule.score_min
        new_max = body.score_max if body.score_max is not None else rule.score_max
        _validate_window(new_min, new_max)
        rule.score_min = new_min
        rule.score_max = new_max
    if body.is_active is not None:
        rule.is_active = 1 if body.is_active else 0

    db.commit()
    db.refresh(rule)
    return RuleOut(**_to_rule_out(rule))


@router.post("/evaluate")
def evaluate(
    tenant: Tenant = Depends(require_tenant_scope),
    db: Session = Depends(get_db),
    role: str = Depends(require_role("tenant_admin")),
):
    return evaluate_rules(db, tenant.id)
