"""backend/app/routers/meta.py - a "server is running" check, and the details
behind the demo banner shown on every page."""

import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from serving.config import PROTOTYPE_NOTICE

from ..config import SEED_JSON_PATH
from ..deps import get_db, get_role
from ..models import Order
from ..schemas import MetaOut

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


# The data file isn't in the repository - it's 29 MB and has to be built - so a
# fresh copy of the code doesn't have it. This used to crash when the file was
# missing. The banner's whole job is to say "this is a demo", so it must keep
# working even when we don't know where the data came from.
_UNKNOWN = "unknown - serving/output/orders_seed.json not present"


def _seed_meta() -> dict:
    try:
        with open(SEED_JSON_PATH) as f:
            return json.load(f)["meta"]
    except (OSError, ValueError, KeyError):
        return {
            "generated_at": _UNKNOWN,
            "model": _UNKNOWN,
            "tenants": [],
            "notice": PROTOTYPE_NOTICE,
        }


@router.get("/meta", response_model=MetaOut)
def get_meta(db: Session = Depends(get_db), role: str = Depends(get_role)):
    seed_meta = _seed_meta()

    n_orders = db.query(func.count(Order.order_id)).scalar()

    return MetaOut(
        generated_at=seed_meta["generated_at"],
        model=seed_meta["model"],
        n_orders=n_orders,
        achieved_overall_auc=seed_meta.get("achieved_overall_auc"),
        achieved_cold_customer_auc=seed_meta.get("achieved_cold_customer_auc"),
        tenants=seed_meta["tenants"],
        notice=seed_meta["notice"],
    )
