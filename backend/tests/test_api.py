"""backend/tests/test_api.py - tests for the server's pages, using a
throwaway database.

Each test uses one of the logged-in clients from conftest.py - analyst,
tenant_admin, other_analyst, platform_admin, or anon (not logged in). Logging
in itself is tested in test_auth.py.

Run from the main project folder: .venv/bin/pytest backend/tests -v
"""

import pytest

from backend.app.constants import ACTION_TYPES
from backend.app.db import SessionLocal
from backend.app.routers import meta as meta_router
from backend.app.models import BaselineStat, Order, OrderStatus, Tenant

RULE_BODY = {"name": "r1", "score_min": 0.7, "score_max": 0.95, "action_type": "call_customer"}


def test_health_is_reachable_without_a_session(anon):
    """This must work without logging in. run_dev.sh checks it to see whether
    the server has started - if it needed a login, run_dev.sh would wrongly
    report that the server failed to start."""
    r = anon.get("/api/health")
    assert r.status_code == 200
    assert "set-cookie" not in {k.lower() for k in r.headers}


def test_list_orders(analyst):
    r = analyst.get("/api/orders")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["order_id"] == "TEST-ORD-000001"


def test_order_detail_omits_ground_truth(analyst):
    r = analyst.get("/api/orders/TEST-ORD-000001")
    assert r.status_code == 200
    assert "is_returned_ground_truth" not in r.json()


def test_unknown_order_404(analyst):
    r = analyst.get("/api/orders/NOPE-000000")
    assert r.status_code == 404


def test_override_writes_both_tables(analyst):
    r = analyst.post(
        "/api/orders/TEST-ORD-000001/override",
        json={"new_score": 0.1, "reason": "test override"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["current_score"] == 0.1
    assert body["status"] == "overridden"
    # Who did it comes from the login. The request doesn't say who it's from,
    # and there's no way to slip a different name in.
    assert body["overridden_by"] == "analyst"

    hist = analyst.get("/api/orders/TEST-ORD-000001/history")
    assert hist.status_code == 200
    events = hist.json()
    override = next(e for e in events if e["event_type"] == "override")
    assert override["new_score"] == 0.1
    assert override["actor_role"] == "ops_analyst"
    assert override["actor_name"] == "analyst"


def test_role_gate_403_then_201(analyst, tenant_admin):
    denied = analyst.post("/api/rules?tenant=test-tenant", json=RULE_BODY)
    assert denied.status_code == 403

    allowed = tenant_admin.post("/api/rules?tenant=test-tenant", json=RULE_BODY)
    assert allowed.status_code == 201
    body = allowed.json()
    assert body["score_min"] == 0.7
    assert body["score_max"] == 0.95


def test_tenant_admin_cannot_write_another_tenants_rules(tenant_admin, platform_admin):
    """A company admin only sees their own company's rules - that's what the
    role is for. (Both test companies are set up in conftest.py.)
    """
    r = tenant_admin.post("/api/rules?tenant=other-tenant", json=RULE_BODY)
    assert r.status_code == 403

    # The platform admin is the only role that may see every company's.
    r = platform_admin.post("/api/rules?tenant=other-tenant", json=RULE_BODY)
    assert r.status_code == 201


def test_tenant_admin_only_lists_own_rules(tenant_admin, platform_admin):
    r = tenant_admin.get("/api/rules")
    assert r.status_code == 200
    assert {row["tenant_slug"] for row in r.json()} == {"test-tenant"}

    r = platform_admin.get("/api/rules")
    assert {"test-tenant", "other-tenant"} <= {row["tenant_slug"] for row in r.json()}


def test_rule_window_must_be_ordered(tenant_admin):
    r = tenant_admin.post(
        "/api/rules?tenant=test-tenant",
        json={"name": "bad", "score_min": 0.9, "score_max": 0.2, "action_type": "call_customer"},
    )
    assert r.status_code == 422


def test_rule_sweep_respects_the_window(tenant_admin):
    """The test order scores 0.9. A rule for a range entirely below that must
    not touch it - which is the point of using a range rather than a minimum."""
    created = tenant_admin.post(
        "/api/rules?tenant=test-tenant",
        json={"name": "low band", "score_min": 0.1, "score_max": 0.3,
              "action_type": "send_reminder_email"},
    ).json()

    # Turn off every other rule, so only the low-range one runs.
    for rule in tenant_admin.get("/api/rules").json():
        if rule["id"] != created["id"]:
            tenant_admin.patch(f"/api/rules/{rule['id']}", json={"is_active": False})

    swept = tenant_admin.post("/api/rules/evaluate?tenant=test-tenant")
    assert swept.status_code == 200
    assert swept.json()["actions_created"] == 0


def test_proceed_with_delivery_is_a_valid_action(analyst, tenant_admin):
    """"Approved for delivery" works as an action, both by hand and in a rule."""
    r = analyst.post(
        "/api/orders/TEST-ORD-000001/actions",
        json={"action_type": "proceed_with_delivery", "note": "reviewed, looks fine"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["action_type"] == "proceed_with_delivery"

    r = tenant_admin.post(
        "/api/rules?tenant=test-tenant",
        json={"name": "clear low band", "score_min": 0.0, "score_max": 0.2,
              "action_type": "proceed_with_delivery"},
    )
    assert r.status_code == 201


def test_ops_analyst_is_pinned_to_its_own_tenant(analyst, other_analyst, platform_admin):
    """An analyst can't see another company's orders - not by asking for them
    with ?tenant=, and not by order number.

    Uses two separately logged-in accounts, so this really tests that the
    server keeps companies apart.
    """
    db = SessionLocal()
    other = db.query(Tenant).filter(Tenant.slug == "other-tenant").first()
    if db.query(Order).filter(Order.order_id == "OTHER-ORD-000001").first() is None:
        o = Order(
            order_id="OTHER-ORD-000001", tenant_id=other.id, customer_ref="c9", product_ref="p9",
            order_date="2021-10-16", model_risk_score=0.5, reasons_json='["x"]',
            customer_no_history=0, product_no_history=0, customer_return_rate=0.1,
            product_return_rate=0.1, avg_discount_value=1.0, avg_gbp_price=2.0,
            country_bucket="Country_B", product_brand_bucket="Brand_B",
            product_type_bucket="productType_B", raw_features_json="{}",
            is_returned_ground_truth=0,
        )
        db.add(o)
        db.add(OrderStatus(order_id=o.order_id, current_score=0.5, status="pending"))
    db.commit()
    db.close()

    # With no company named, they get only their own company's orders.
    rows = analyst.get("/api/orders").json()["items"]
    assert rows, "analyst should still see their own tenant's orders"
    assert {r["tenant"] for r in rows} == {"Test Tenant"}

    # Asking for another company is refused with an error, not quietly ignored.
    assert analyst.get("/api/orders?tenant=other-tenant").status_code == 403

    # And another company's order can't be opened by its number.
    assert analyst.get("/api/orders/OTHER-ORD-000001").status_code == 404
    assert analyst.post(
        "/api/orders/OTHER-ORD-000001/actions",
        json={"action_type": "call_customer"},
    ).status_code == 404

    # A different logged-in account sees only its own company.
    other_rows = other_analyst.get("/api/orders").json()["items"]
    assert {r["tenant"] for r in other_rows} == {"Other Tenant"}

    # The platform admin still sees every company.
    admin_rows = platform_admin.get("/api/orders").json()["items"]
    assert {"Test Tenant", "Other Tenant"} <= {r["tenant"] for r in admin_rows}


def test_period_filter_counts_back_from_the_latest_order_in_scope(analyst, platform_admin):
    """The dates are made up and end in 2021, so "the last N days" counts back
    from the newest order this user can see - counting from today would find
    nothing. Both the first and last day are included."""
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.slug == "test-tenant").first()
    other = db.query(Tenant).filter(Tenant.slug == "other-tenant").one()

    def add(order_id, tenant_id, order_date):
        if db.query(Order).filter(Order.order_id == order_id).first() is not None:
            return
        db.add(Order(
            order_id=order_id, tenant_id=tenant_id, customer_ref="cd", product_ref="pd",
            order_date=order_date, model_risk_score=0.4, reasons_json='["x"]',
            customer_no_history=0, product_no_history=0, customer_return_rate=0.1,
            product_return_rate=0.1, avg_discount_value=1.0, avg_gbp_price=2.0,
            country_bucket="Country_C", product_brand_bucket="Brand_C",
            product_type_bucket="productType_C", raw_features_json="{}",
            is_returned_ground_truth=0,
        ))
        db.add(OrderStatus(order_id=order_id, current_score=0.4, status="pending"))

    add("TEST-ORD-NEWEST", tenant.id, "2021-10-20")
    add("TEST-ORD-OLDEST", tenant.id, "2021-09-01")
    # Later than anything in test-tenant on purpose, to prove each user's
    # "today" comes from their own company's orders, not from every order.
    add("OTHER-ORD-LATEST", other.id, "2021-12-01")
    db.commit()
    db.close()

    unfiltered = analyst.get("/api/orders?page_size=200").json()
    assert unfiltered["reference_date"] == "2021-10-20"
    assert unfiltered["since_date"] is None
    assert {"TEST-ORD-NEWEST", "TEST-ORD-OLDEST"} <= {i["order_id"] for i in unfiltered["items"]}

    # 1 day means just the newest day itself.
    one_day = analyst.get("/api/orders?last_n_days=1&page_size=200").json()
    assert one_day["since_date"] == "2021-10-20"
    assert {i["order_id"] for i in one_day["items"]} == {"TEST-ORD-NEWEST"}

    # 7 days means 14-20 October 2021, so the order on the 15th is included
    # and the one on 1 September isn't.
    week = analyst.get("/api/orders?last_n_days=7&page_size=200").json()
    assert week["since_date"] == "2021-10-14"
    ids = {i["order_id"] for i in week["items"]}
    assert "TEST-ORD-NEWEST" in ids and "TEST-ORD-000001" in ids
    assert "TEST-ORD-OLDEST" not in ids

    # A long period includes everything for their company, and nothing from another.
    wide = analyst.get("/api/orders?last_n_days=365&page_size=200").json()
    assert wide["total"] == unfiltered["total"]
    assert "OTHER-ORD-LATEST" not in {i["order_id"] for i in wide["items"]}

    # The platform admin sees every company, so their "today" is later.
    admin = platform_admin.get("/api/orders?last_n_days=1&page_size=200").json()
    assert admin["reference_date"] == "2021-12-01"
    assert {i["order_id"] for i in admin["items"]} == {"OTHER-ORD-LATEST"}


def test_period_filter_rejects_a_nonsense_window(analyst):
    assert analyst.get("/api/orders?last_n_days=0").status_code == 422
    assert analyst.get("/api/orders?last_n_days=99999").status_code == 422


# --- check every page loads -------------------------------------------------
#
# These exist because the alerts page once broke without any test noticing: a
# change removed a line it needed, and no test ever loaded that page. Simply
# checking that every page loads is cheap, and it catches a whole family of
# mistakes - missing imports, typos, things that stopped connecting.

READ_ENDPOINTS_ANY_ROLE = [
    "/api/meta",
    "/api/tenants",
    "/api/orders",
    "/api/orders/score-histogram",
    "/api/orders/TEST-ORD-000001",
    "/api/orders/TEST-ORD-000001/history",
    "/api/alerts",
    "/api/dashboard",
    "/api/rules",
    "/api/reporting/baseline-vs-actual",
]

READ_ENDPOINTS_TENANT_ADMIN = ["/api/audit-log", "/api/escalations"]


# --- the risk chart above the order list -----------------------------------
#
# These check that the chart agrees with the order list, rather than checking
# fixed numbers. Earlier tests change scores and run rules, so a test expecting
# an exact score would pass on its own but fail alongside the others. What
# matters is that the chart and the list always agree, whatever has changed.


def _histogram(client, query=""):
    r = client.get(f"/api/orders/score-histogram{query}")
    assert r.status_code == 200, r.text
    return r.json()


def test_score_histogram_covers_the_same_orders_as_the_queue(analyst):
    """The chart must count the same orders the list shows - otherwise it's
    misleading about the list beneath it."""
    listed = analyst.get("/api/orders").json()["total"]
    body = _histogram(analyst)

    assert len(body["buckets"]) == 20
    assert body["total"] == listed
    assert sum(b["count"] for b in body["buckets"]) == listed


def test_score_histogram_buckets_each_order_by_its_current_score(analyst):
    """Every order in the list is counted in the right bar for its score."""
    rows = analyst.get("/api/orders?page_size=200").json()["items"]
    buckets = _histogram(analyst)["buckets"]

    expected = [0] * 20
    for row in rows:
        # A score of 1.0 goes in the top bar, not one past the end.
        expected[min(int(row["current_score"] * 20), 19)] += 1

    assert [b["count"] for b in buckets] == expected


def test_score_histogram_ignores_the_score_window(analyst):
    """The score range is what the user picks on the chart, so the chart must
    still show the orders outside it - otherwise the selection would always
    look like it covered everything."""
    assert _histogram(analyst, "?min_score=0.1&max_score=0.2") == _histogram(analyst)


def test_score_histogram_honours_every_other_filter(analyst):
    """Any other filter that shortens the list shrinks the chart too."""
    for query in ("?status=pending", "?country=Country_A", "?cold_start=true"):
        listed = analyst.get(f"/api/orders{query}").json()["total"]
        assert _histogram(analyst, query)["total"] == listed

    assert _histogram(analyst, "?country=Country_B")["total"] == 0


def test_score_histogram_is_scoped_to_the_callers_tenant(other_analyst):
    listed = other_analyst.get("/api/orders").json()["total"]
    assert _histogram(other_analyst)["total"] == listed


def test_score_histogram_rejects_an_unknown_status(analyst):
    assert analyst.get("/api/orders/score-histogram?status=nonsense").status_code == 422


@pytest.mark.parametrize("path", READ_ENDPOINTS_ANY_ROLE)
def test_read_endpoints_respond_for_an_analyst(analyst, path):
    r = analyst.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"


@pytest.mark.parametrize("path", READ_ENDPOINTS_ANY_ROLE + READ_ENDPOINTS_TENANT_ADMIN)
def test_read_endpoints_respond_for_the_platform_admin(platform_admin, path):
    """Tested separately for the platform admin, because they see every
    company at once - a different path through the code."""
    r = platform_admin.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"


@pytest.mark.parametrize("path", READ_ENDPOINTS_TENANT_ADMIN)
def test_tenant_admin_only_reads_are_refused_for_an_analyst(analyst, path):
    assert analyst.get(path).status_code == 403


def test_meta_survives_a_missing_seed_file(analyst, monkeypatch):
    """A fresh copy of the code has no data file (it's 29 MB and has to be
    built), and this page used to crash without it. The demo banner relies on
    this page, and its whole job is to say "this is a demo" - so it must keep
    working even when the data file is missing."""
    monkeypatch.setattr(meta_router, "SEED_JSON_PATH", "/nonexistent/orders_seed.json")

    r = analyst.get("/api/meta")

    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "PROTOTYPE" in body["notice"]
    assert "not present" in body["generated_at"]
    assert body["n_orders"] >= 0          # still read from the database


def test_alerts_computes_a_spike_and_scopes_it(platform_admin, analyst, db_session):
    """A group whose recent return rate is far above normal must trigger an
    alert - and only for the company it belongs to."""
    tenant = db_session.query(Tenant).filter(Tenant.slug == "test-tenant").one()

    # A baseline of 0% against a window of all-returned orders, with enough
    # rows to clear ALERT_MIN_N.
    db_session.add(BaselineStat(
        tenant_id=tenant.id, cohort_type="country", cohort_key="Country_Z",
        baseline_return_rate=0.0, n_baseline_orders=100,
    ))
    for i in range(20):
        oid = f"SPIKE-ORD-{i:06d}"
        db_session.add(Order(
            order_id=oid, tenant_id=tenant.id, customer_ref="cs", product_ref="ps",
            order_date="2021-10-15", model_risk_score=0.5, reasons_json='["x"]',
            customer_no_history=0, product_no_history=0, customer_return_rate=0.1,
            product_return_rate=0.1, avg_discount_value=1.0, avg_gbp_price=2.0,
            country_bucket="Country_Z", product_brand_bucket="Brand_A",
            product_type_bucket="productType_A", raw_features_json="{}",
            is_returned_ground_truth=1,
        ))
        db_session.add(OrderStatus(order_id=oid, current_score=0.5, status="pending"))
    db_session.commit()

    try:
        alerts = analyst.get("/api/alerts").json()
        spike = next(a for a in alerts
                     if a["cohort_type"] == "country" and a["cohort_key"] == "Country_Z")
        assert spike["n_orders"] >= 15
        assert spike["gap"] > 0.15
        assert spike["severity"] == "high"
        assert spike["tenant"] == "Test Tenant"

        # the spike belongs to one tenant: the admin sees it, and sees it
        # attributed to Test Tenant and to nobody else
        admin_hits = [a for a in platform_admin.get("/api/alerts").json()
                      if a["cohort_key"] == "Country_Z"]
        assert admin_hits, "the platform admin should see it too"
        assert {a["tenant"] for a in admin_hits} == {"Test Tenant"}
    finally:
        db_session.query(OrderStatus).filter(
            OrderStatus.order_id.like("SPIKE-ORD-%")).delete(synchronize_session=False)
        db_session.query(Order).filter(
            Order.order_id.like("SPIKE-ORD-%")).delete(synchronize_session=False)
        db_session.query(BaselineStat).filter(
            BaselineStat.cohort_key == "Country_Z").delete(synchronize_session=False)
        db_session.commit()



def test_action_outcome_closes_the_order(analyst):
    """Recording how an action turned out (it used to be the one way of
    changing data that no test tried)."""
    created = analyst.post(
        "/api/orders/TEST-ORD-000001/actions",
        json={"action_type": "call_customer", "note": "ringing the customer"},
    )
    assert created.status_code == 201, created.text
    log_id = created.json()["id"]

    r = analyst.patch(
        f"/api/orders/TEST-ORD-000001/actions/{log_id}",
        json={"outcome": "resolved_prevented", "note": "customer confirmed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "resolved_prevented"

    detail = analyst.get("/api/orders/TEST-ORD-000001").json()
    assert detail["status"] == "closed"


def test_platform_admin_can_onboard_a_tenant(platform_admin, analyst):
    r = platform_admin.post("/api/tenants", json={"name": "Smoke Test Brand"})
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "smoke-test-brand"

    # A duplicate is refused, rather than quietly making a second one.
    assert platform_admin.post("/api/tenants", json={"name": "Smoke Test Brand"}).status_code == 409
    # And an analyst can't add companies at all.
    assert analyst.post("/api/tenants", json={"name": "Nope"}).status_code == 403


# --- escalations: an analyst passing an order to their company admin -------

def test_escalate_is_a_valid_action_and_lands_in_the_admin_queue(analyst, tenant_admin):
    """Escalating is an action like any other - the only difference is who
    it's aimed at."""
    raised = analyst.post(
        "/api/orders/TEST-ORD-000001/actions",
        json={"action_type": "escalate", "note": "customer disputes the address"},
    )
    assert raised.status_code == 201, raised.text
    log_id = raised.json()["id"]
    assert raised.json()["outcome"] == "pending"

    rows = tenant_admin.get("/api/escalations")
    assert rows.status_code == 200, rows.text
    row = next(r for r in rows.json() if r["log_id"] == log_id)
    assert row["order_id"] == "TEST-ORD-000001"
    assert row["note"] == "customer disputes the address"
    assert row["raised_by_role"] == "ops_analyst"
    assert row["raised_by"] == "analyst"
    assert row["outcome"] == "pending"


def test_the_escalation_queue_is_not_visible_to_an_analyst(analyst):
    """Analysts raise escalations; working through them is the company admin's
    job - that's the point of passing them up."""
    assert analyst.get("/api/escalations").status_code == 403


def test_escalations_are_scoped_to_one_tenant(other_analyst, tenant_admin, platform_admin):
    other_analyst.post(
        "/api/orders/OTHER-ORD-000001/actions",
        json={"action_type": "escalate", "note": "raised at the other tenant"},
    )
    mine = tenant_admin.get("/api/escalations").json()
    assert "OTHER-ORD-000001" not in {r["order_id"] for r in mine}
    assert {r["tenant"] for r in mine} == {"Test Tenant"}

    # The platform admin sees every company's.
    everyones = platform_admin.get("/api/escalations").json()
    assert "OTHER-ORD-000001" in {r["order_id"] for r in everyones}


def test_resolving_an_escalation_clears_it_from_the_open_queue(analyst, tenant_admin):
    raised = analyst.post(
        "/api/orders/TEST-ORD-000001/actions",
        json={"action_type": "escalate", "note": "needs a decision"},
    )
    log_id = raised.json()["id"]
    assert log_id in {r["log_id"] for r in tenant_admin.get("/api/escalations").json()}

    # Closed the same way as any other action - escalations don't need
    # anything special.
    done = tenant_admin.patch(
        f"/api/orders/TEST-ORD-000001/actions/{log_id}",
        json={"outcome": "resolved_prevented", "note": "spoke to the customer"},
    )
    assert done.status_code == 200, done.text

    open_now = {r["log_id"] for r in tenant_admin.get("/api/escalations").json()}
    assert log_id not in open_now

    with_resolved = tenant_admin.get("/api/escalations?include_resolved=true").json()
    row = next(r for r in with_resolved if r["log_id"] == log_id)
    assert row["outcome"] == "resolved_prevented"


def test_a_rule_cannot_be_set_to_escalate(tenant_admin):
    """Escalating is a decision made one order at a time. A rule must not be
    able to do it to thousands of orders at once - the company admin would be
    handed more than anyone could deal with."""
    r = tenant_admin.post(
        "/api/rules?tenant=test-tenant",
        json={"name": "auto escalate", "score_min": 0.9, "score_max": 1.0,
              "action_type": "escalate"},
    )
    assert r.status_code == 422
    assert "escalate" not in r.json()["detail"]

    # But an analyst can still do it by hand.
    created = tenant_admin.post(
        "/api/rules?tenant=test-tenant",
        json={"name": "auto call", "score_min": 0.9, "score_max": 1.0,
              "action_type": "call_customer"},
    )
    assert created.status_code == 201

    # And changing an existing rule to escalate is refused too.
    patched = tenant_admin.patch(
        f"/api/rules/{created.json()['id']}", json={"action_type": "escalate"},
    )
    assert patched.status_code == 422


# --- the dashboard's front-page numbers ------------------------------------
#
# These check that the dashboard agrees with the order list and the
# escalations list, rather than checking fixed numbers. Earlier tests change
# scores, log actions and run rules, so a fixed count would pass on its own but
# fail alongside the others. What matters is that they always agree.


def _dashboard(client, query=""):
    r = client.get(f"/api/dashboard{query}")
    assert r.status_code == 200, r.text
    return r.json()


def test_dashboard_order_counts_match_the_queue(analyst):
    for query in ("", "?last_n_days=7"):
        dash = _dashboard(analyst, query)["orders"]
        queue = analyst.get(f"/api/orders?page_size=1{query.replace('?', '&')}").json()

        assert dash["total"] == queue["total"]
        mix = dash["risk_mix"]
        # Every score falls in exactly one of the three bands. If the totals
        # don't add up, a band's cut-off has moved.
        assert mix["low"] + mix["medium"] + mix["high"] == dash["total"]
        assert 0 <= dash["cold_start"] <= dash["total"]


def test_dashboard_reports_the_same_window_as_the_queue(analyst, platform_admin):
    for client in (analyst, platform_admin):
        dash = _dashboard(client, "?last_n_days=14")["orders"]
        queue = client.get("/api/orders?page_size=1&last_n_days=14").json()
        assert dash["reference_date"] == queue["reference_date"]
        assert dash["since_date"] == queue["since_date"]
        assert dash["last_n_days"] == 14


def test_dashboard_action_counts_come_from_the_log_not_the_status(analyst):
    """order_status only keeps the latest status. An order that was flagged
    and then approved only shows the latest - so both numbers must come from
    the action history, or the earlier action would vanish."""
    before = _dashboard(analyst)["actions"]

    for action in ("flag_for_manual_review", "proceed_with_delivery"):
        r = analyst.post(
            "/api/orders/TEST-ORD-000001/actions",
            json={"action_type": action, "note": "dashboard counting test"},
        )
        assert r.status_code == 201, r.text

    after = _dashboard(analyst)["actions"]
    detail = analyst.get("/api/orders/TEST-ORD-000001").json()
    assert detail["status"] == "actioned", "one status string, as expected"

    # Checked as "at least", not "went up by one", on purpose. These count each
    # order once, and an earlier test already approved this same order - so
    # approving it again changes nothing. That's correct, not a mistake.
    #
    # What matters is that ONE order is counted under BOTH actions, even though
    # its status only shows one. Counting from the status column couldn't do
    # that - so this test fails if anyone later "simplifies" these numbers to
    # use it.
    assert after["orders_flagged_for_manual_review"] >= 1
    assert after["orders_cleared_for_delivery"] >= 1
    # Both actions were recorded, even though only one is counted in a box.
    assert after["total_actions_logged"] == before["total_actions_logged"] + 2


def test_dashboard_counts_an_order_once_however_many_actions_it_carries(analyst):
    before = _dashboard(analyst)["actions"]

    for _ in range(2):
        r = analyst.post(
            "/api/orders/TEST-ORD-000001/actions",
            json={"action_type": "send_reminder_email", "note": "twice"},
        )
        assert r.status_code == 201, r.text

    after = _dashboard(analyst)["actions"]
    # Two actions on one order: the action count goes up by two, and the order
    # counts don't secretly count actions instead.
    assert after["total_actions_logged"] == before["total_actions_logged"] + 2
    assert after["open_actions"] == before["open_actions"] + 2


def test_dashboard_open_interventions_close_with_the_outcome(analyst):
    r = analyst.post(
        "/api/orders/TEST-ORD-000001/actions",
        json={"action_type": "proceed_with_delivery", "note": "cleared"},
    )
    assert r.status_code == 201, r.text
    log_id = r.json()["id"]

    opened = _dashboard(analyst)["actions"]
    by_type = {row["action_type"]: row["open_actions"] for row in opened["open_by_action_type"]}
    # Every action starts as open - even "approved for delivery". That's why
    # the website always shows a note explaining this number.
    assert by_type["proceed_with_delivery"] >= 1

    patched = analyst.patch(
        f"/api/orders/TEST-ORD-000001/actions/{log_id}",
        json={"outcome": "resolved_prevented"},
    )
    assert patched.status_code == 200, patched.text

    closed = _dashboard(analyst)["actions"]
    assert closed["open_actions"] == opened["open_actions"] - 1
    # Closing an action doesn't undo it - the record of what was done stays.
    assert closed["total_actions_logged"] == opened["total_actions_logged"]
    assert closed["orders_cleared_for_delivery"] == opened["orders_cleared_for_delivery"]


def test_dashboard_open_escalations_match_the_escalations_queue(analyst, tenant_admin):
    r = analyst.post(
        "/api/orders/TEST-ORD-000001/actions",
        json={"action_type": "escalate", "note": "please review"},
    )
    assert r.status_code == 201, r.text

    dash = _dashboard(tenant_admin)["actions"]
    queue = tenant_admin.get("/api/escalations").json()
    # Both use the same definition from services/escalations.py. If someone
    # changes one and not the other, this test catches it.
    assert dash["orders_escalated_and_open"] == len({row["order_id"] for row in queue})


def test_dashboard_total_actions_logged_is_the_empty_state_discriminator(analyst):
    actions = _dashboard(analyst)["actions"]
    assert actions["total_actions_logged"] >= actions["open_actions"]
    if actions["total_actions_logged"] == 0:
        assert actions["orders_cleared_for_delivery"] == 0
        assert actions["orders_flagged_for_manual_review"] == 0
        assert actions["orders_escalated_and_open"] == 0
        assert actions["open_actions"] == 0


def test_dashboard_is_quiet_and_200_for_a_tenant_with_nothing_in_it(platform_admin):
    """A company with no orders yet - like a brand-new one. Every total here is
    worked out over nothing, which gives an empty value rather than zero, so
    this test catches the page crashing when it should just show zeros."""
    created = platform_admin.post("/api/tenants", json={"name": "Empty Brand"})
    assert created.status_code in (201, 409), created.text

    dash = _dashboard(platform_admin, "?tenant=empty-brand&last_n_days=30")

    orders = dash["orders"]
    assert orders["total"] == 0
    assert orders["risk_mix"] == {"low": 0, "medium": 0, "high": 0}
    assert orders["cold_start"] == 0
    # No orders means no "today", so there's no date range to report, even
    # though one was asked for. Nothing later may assume there's a date.
    assert orders["reference_date"] is None
    assert orders["since_date"] is None

    actions = dash["actions"]
    assert actions["total_actions_logged"] == 0
    assert actions["open_actions"] == 0
    assert actions["orders_cleared_for_delivery"] == 0
    assert actions["orders_flagged_for_manual_review"] == 0
    assert actions["orders_escalated_and_open"] == 0
    # Every action type is listed, at zero, rather than the list being empty.
    assert len(actions["open_by_action_type"]) == len(ACTION_TYPES)


def test_dashboard_is_scoped_to_the_callers_tenant(analyst, other_analyst, platform_admin):
    mine = _dashboard(analyst)["orders"]["total"]
    theirs = _dashboard(other_analyst)["orders"]["total"]
    everyone = _dashboard(platform_admin)["orders"]["total"]

    assert mine == analyst.get("/api/orders?page_size=1").json()["total"]
    assert theirs == other_analyst.get("/api/orders?page_size=1").json()["total"]
    assert mine + theirs <= everyone

    # Refused with an error, not quietly limited to their own company -
    # success would make them think they'd seen the other company's data.
    assert analyst.get("/api/dashboard?tenant=other-tenant").status_code == 403


def test_dashboard_rejects_a_nonsense_window(analyst):
    assert analyst.get("/api/dashboard?last_n_days=0").status_code == 422
    assert analyst.get("/api/dashboard?last_n_days=99999").status_code == 422
