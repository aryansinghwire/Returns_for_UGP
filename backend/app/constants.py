"""backend/app/constants.py - fixed lists of allowed values: actions,
outcomes, order statuses and roles.

Many of these are saved in the database, so don't rename them - see
CONTRIBUTING.md."""

ACTION_TYPES = {
    "call_customer",
    "send_confirmation_sms",
    "send_reminder_email",
    "flag_for_manual_review",
    "convert_cod_to_prepaid",
    # "Checked it, send it." Approving an order is a real decision, so it's
    # recorded like any other action.
    "proceed_with_delivery",
    # Passes the order to the company's admin instead of dealing with it.
    # It's the only action aimed at another person, and it's what fills the
    # admin's escalations list (routers/escalations.py).
    "escalate",
}

# What an automatic rule is allowed to do. "escalate" is left out on purpose:
# a rule could pass thousands of orders to one admin in a single click, more
# than anyone could handle. Escalating stays a choice made one order at a time.
RULE_ACTION_TYPES = ACTION_TYPES - {"escalate"}

OUTCOMES = {"pending", "resolved_kept", "resolved_prevented", "no_response"}

CLOSING_OUTCOMES = {"resolved_kept", "resolved_prevented", "no_response"}

ORDER_STATUSES = {"pending", "overridden", "actioned", "closed"}

# Only "label" is used - it's the role name shown in the account menu
# (routers/auth.py sends it). The descriptions aren't shown anywhere; they're
# kept as a plain explanation of what each role is for.
ROLES = {
    "ops_analyst": {
        "label": "Ops Analyst",
        "description": "Reviews the risk queue, drills into orders, applies manual overrides and logs interventions.",
    },
    "tenant_admin": {
        "label": "Tenant Admin",
        "description": "Everything an Ops Analyst can do, for their own tenant only: configuring that tenant's automated score windows, alerts, and audit log.",
    },
    "admin": {
        "label": "Platform Admin (Support)",
        "description": "Cross-tenant. Everything a Tenant Admin can do for any tenant, plus onboarding new tenants.",
    },
}


# --- DEMO ONLY ---------------------------------------------------------------
# A fixed admin login that comes with the code, is created when the server
# starts, and is shown on the login page. The login page, the database loader
# and run_dev.sh all read it from here, so they always agree.
#
# This is on purpose: the demo should work for anyone given the link. But it
# means this build must never hold real data. The address ends in .local,
# which is reserved and can never reach a real mailbox.
DEMO_ADMIN_EMAIL = "admin@returns-demo.local"
DEMO_ADMIN_PASSWORD = "returns-demo-admin"
# The demo admin's old email address, from before the project was renamed.
# Kept so bootstrap.ensure_demo_admin can find an old account and update it,
# instead of creating a second admin alongside it. Don't rename this.
LEGACY_DEMO_ADMIN_EMAIL = "admin@rto-demo.local"
DEMO_ADMIN_DISPLAY_NAME = "Platform Admin (demo)"
DEMO_ADMIN_NOTICE = (
    "PROTOTYPE - this platform-admin account ships with the code and its password "
    "is printed on the sign-in page. Signup also lets anyone choose their own role "
    "for any listed tenant. Neither is how a real deployment works; both exist so "
    "the role model can be demonstrated without an invite flow."
)
