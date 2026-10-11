#!/usr/bin/env python3
"""
backend/scripts/seed_db.py - loads the scored orders from
serving/output/orders_seed.json into the database.

If the database already has orders, it stops rather than loading them twice -
unless you add --force, which empties every table first. It also works out
each group's normal return rate (baseline_stats), and makes sure the demo
admin account exists.

Run from the main project folder:
    .venv/bin/python -m backend.scripts.seed_db
    .venv/bin/python -m backend.scripts.seed_db --force
"""

import json
import os
import re
import sys

from sqlalchemy import func

from ..app.bootstrap import ensure_demo_admin
from ..app.config import SEED_JSON_PATH
from ..app.db import Base, SessionLocal, engine
from ..app.models import BaselineStat, Order, OrderStatus, Tenant


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def seed(force: bool = False):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # This is called twice, and both are needed. This first one runs even
        # if the database is already loaded, so there's always someone who can
        # log in. The second (further down) is needed because --force deletes
        # every table, users included.
        ensure_demo_admin(db)
        db.commit()

        existing = db.query(func.count(Order.order_id)).scalar()
        if existing and not force:
            print(f"DB already has {existing:,} orders - pass --force to wipe and reseed.")
            print("ensured the demo platform-admin account exists.")
            return

        if existing and force:
            print("wiping existing tables...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)

        # If the data file is missing, say so plainly and say how to make it -
        # the same message run_dev.sh gives. Otherwise you'd get a confusing
        # error that looks like a bug in this script.
        if not os.path.exists(SEED_JSON_PATH):
            sys.exit(
                f"{SEED_JSON_PATH} is missing.\n"
                "Generate it first:  python serving/export_seed.py\n"
                "(this retrains GraphSAGE and rescores the test edges - it takes a while)"
            )

        with open(SEED_JSON_PATH) as f:
            doc = json.load(f)
        meta = doc["meta"]
        orders = doc["orders"]
        print(f"loaded {len(orders):,} orders from {SEED_JSON_PATH} "
              f"(model={meta['model']}, achieved_overall_auc={meta['achieved_overall_auc']})")

        tenant_by_name = {}
        for name in meta["tenants"]:
            tenant = Tenant(name=name, slug=slugify(name))
            db.add(tenant)
            tenant_by_name[name] = tenant
        db.flush()  # gives each company its ID, without saving yet

        print(f"created {len(tenant_by_name)} tenants: "
              f"{[(t.name, t.slug) for t in tenant_by_name.values()]}")

        stage_orders(db, orders, tenant_by_name)
        db.commit()
        print(f"committed {len(orders):,} orders + status rows")

        compute_baseline_stats(db)
        print("computed baseline_stats")

        # The second of the two calls. --force deleted every table, users
        # included, so the admin account has to be put back. Accounts people
        # created by signing up are gone too - which is right, because the
        # companies they belonged to have just been recreated with new IDs.
        ensure_demo_admin(db)
        db.commit()
        print("ensured the demo platform-admin account exists")

    finally:
        db.close()


def stage_orders(db, orders, tenant_by_name):
    """Add each order, plus its matching status row.

    Sends them to the database every 4,000 orders rather than all 16,000 at
    once. That keeps memory use down, and if a row is bad, the error appears
    near that row instead of only at the end. The caller saves the result.
    """
    for i, rec in enumerate(orders):
        db.add(Order(
            order_id=rec["order_id"],
            tenant_id=tenant_by_name[rec["tenant"]].id,
            customer_ref=rec["customer_ref"],
            product_ref=rec["product_ref"],
            order_date=rec["order_date"],
            model_risk_score=rec["risk_score"],
            reasons_json=json.dumps(rec["reasons"]),
            customer_no_history=rec["customer_no_history"],
            product_no_history=rec["product_no_history"],
            customer_return_rate=rec["customer_return_rate"],
            product_return_rate=rec["product_return_rate"],
            avg_discount_value=rec["avg_discount_value"],
            avg_gbp_price=rec["avg_gbp_price"],
            country_bucket=rec["country_bucket"],
            product_brand_bucket=rec["product_brand_bucket"],
            product_type_bucket=rec["product_type_bucket"],
            raw_features_json=json.dumps(rec["raw_features"]),
            is_returned_ground_truth=rec["is_returned_ground_truth"],
        ))
        # Every order gets a status straight away, so the order list never has
        # to deal with an order that has none.
        db.add(OrderStatus(
            order_id=rec["order_id"],
            current_score=rec["risk_score"],
            status="pending",
        ))
        if (i + 1) % 4000 == 0:
            db.flush()
            print(f"  ...{i + 1:,} orders staged")


def compute_baseline_stats(db):
    """Work out each group's normal return rate: the average of the
    product's historical return rate, for each company and group.

    This uses real historical data, not the made-up dates or companies.
    services/reporting.py uses the same formula when it has to work one out
    on the spot."""
    cohort_columns = {
        "product": Order.product_ref,
        "country": Order.country_bucket,
        "product_type": Order.product_type_bucket,
    }

    for tenant in db.query(Tenant).all():
        overall_avg, overall_n = (
            db.query(func.avg(Order.product_return_rate), func.count(Order.order_id))
            .filter(Order.tenant_id == tenant.id)
            .one()
        )
        db.add(BaselineStat(
            tenant_id=tenant.id, cohort_type="overall", cohort_key="overall",
            baseline_return_rate=float(overall_avg or 0.0), n_baseline_orders=int(overall_n or 0),
        ))

        for cohort_type, col in cohort_columns.items():
            rows = (
                db.query(col, func.avg(Order.product_return_rate), func.count(Order.order_id))
                .filter(Order.tenant_id == tenant.id)
                .group_by(col)
                .all()
            )
            for key, avg_rate, n in rows:
                db.add(BaselineStat(
                    tenant_id=tenant.id, cohort_type=cohort_type, cohort_key=key,
                    baseline_return_rate=float(avg_rate or 0.0), n_baseline_orders=int(n or 0),
                ))

    db.commit()


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
