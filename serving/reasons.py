"""
serving/reasons.py - writes the short, plain explanations shown next to each
order's risk score ("This customer returns 60% of what they buy", and so on).

These are simple rules on real, named details - not a complex analysis of how
the model reached its score.

Strict rule: never mention the 13 lettered return-reason codes
(cust__customerId_level_return_code_*, prod__variantID_level_return_code_*).
Nobody knows what the letters mean, so they must never be presented as if
they did.

Two more rules:

1. For a customer or product with no history, details like return rate,
   discount and price are filled in with placeholder values (see
   build_features.py). Treating a placeholder as real would turn "we know
   nothing" into a false warning. So customer rules only apply to customers
   with history, and product rules only to products with history.

2. No rule is based on age, year of birth, gender or premium membership
   (cust__age, cust__yearOfBirth, cust__isMale, cust__premier). Staff use these
   explanations to justify acting on an order, and "risky because the customer
   is young" or "is male" isn't something this app should ever say. Premium
   membership is left out because its effect was never measured. The model
   still uses all four; the explanations don't.
"""

from config import (
    HIGH_PERCENTILE,
    HIGH_RETURN_RATE_THRESHOLD,
    HIGH_RISK_SCORE_THRESHOLD,
    LOW_PERCENTILE,
)

# Each rule: (which column, which percentage point, customer or product side).
# The side decides which rows the cut-off is worked out from - only those with
# real history. Including placeholder rows would just give back the placeholder
# value (it did, once: the old discount cut-off landed exactly on it).
THRESHOLD_SPEC = {
    "cust_rate_high":      ("cust__customerReturnRate", HIGH_PERCENTILE, "customer"),
    "cust_rate_low":       ("cust__customerReturnRate", LOW_PERCENTILE,  "customer"),
    "cust_returns_high":   ("cust__returnsPerCustomer", HIGH_PERCENTILE, "customer"),
    "cust_sales_low":      ("cust__salesPerCustomer",   LOW_PERCENTILE,  "customer"),
    "prod_rate_high":      ("prod__productReturnRate",  HIGH_PERCENTILE, "product"),
    "prod_rate_low":       ("prod__productReturnRate",  LOW_PERCENTILE,  "product"),
    "prod_returns_high":   ("prod__returnsPerProduct",  HIGH_PERCENTILE, "product"),
    "prod_sales_low":      ("prod__salesPerProduct",    LOW_PERCENTILE,  "product"),
    "discount_high":       ("prod__avgDiscountValue",   HIGH_PERCENTILE, "product"),
    "price_high":          ("prod__avgGbpPrice",        HIGH_PERCENTILE, "product"),
}

MITIGATING_PREFIX = "Mitigating: "


def compute_thresholds(train_df):
    """Work out every cut-off from the training data only, so the orders shown
    on the dashboard never decide what counts as "high".

    Each one uses only the training rows with real history - see the note on
    THRESHOLD_SPEC.
    """
    thresholds = {}
    for name, (col, q, side) in THRESHOLD_SPEC.items():
        if col not in train_df.columns:
            continue
        flag = f"{side}_no_history"
        rows = train_df[train_df[flag] == 0] if flag in train_df.columns else train_df
        if len(rows) == 0:
            continue
        thresholds[name] = float(rows[col].quantile(q))
    return thresholds


def _get(row, col):
    value = row.get(col)
    return None if value is None else float(value)


def _at_least(value, limit):
    return value is not None and limit is not None and value >= limit


def _at_most(value, limit):
    return value is not None and limit is not None and value <= limit


def _count(value, singular, plural):
    """Write "1 prior purchase" or "4 prior purchases" properly - staff read
    these one order at a time, so "purchase(s)" isn't good enough."""
    return f"{value:,.0f} {singular if round(value) == 1 else plural}"


def _rate_reason(subject, population, rate, typical_floor):
    """The return-rate explanation, at two levels: "high" (a fixed 50% or more)
    and "above the typical range" (in the top quarter, but under 50%).

    The milder wording is only used when the top quarter starts below 50% -
    otherwise the two levels would describe the same orders. On this data that
    splits neatly: for products the top quarter starts at about 38%, so there's
    a real middle band; for customers it starts at about 71%, which is already
    "high". The check is written out so this depends on the data, rather than
    being code that quietly never runs.
    """
    if _at_least(rate, HIGH_RETURN_RATE_THRESHOLD):
        return (f"{subject}'s historical return rate is high "
                f"({rate:.0%}, threshold {HIGH_RETURN_RATE_THRESHOLD:.0%})")
    if (typical_floor is not None and typical_floor < HIGH_RETURN_RATE_THRESHOLD
            and _at_least(rate, typical_floor)):
        return (f"{subject}'s historical return rate is above the typical range "
                f"({rate:.0%}, top quartile of {population} with history starts at "
                f"{typical_floor:.0%})")
    return None


def derive_reasons(row, risk_score, thresholds):
    """The explanations for one order, most important first.

    The order matters: the order list shows the first explanation as the "Top
    reason", so the strongest one must come first. Return-rate history leads,
    because it was measured as the single most telling detail (on its own it
    scores 0.801). "New customer" and "new product" come lower, because the
    list already shows those as their own labels.

    Reasons that LOWER the risk go last, with a label, so they can never push a
    warning out of the "Top reason" spot - but they still explain why a
    low-scoring order is low.
    """
    reasons = []
    mitigating = []
    customer_cold = bool(row.get("customer_no_history"))
    product_cold = bool(row.get("product_no_history"))

    cust_rate = _get(row, "cust__customerReturnRate")
    prod_rate = _get(row, "prod__productReturnRate")

    # --- how often they return things ---
    cust_rate_reason = _rate_reason("Customer", "customers", cust_rate,
                                     thresholds.get("cust_rate_high"))
    if not customer_cold and cust_rate_reason:
        reasons.append(cust_rate_reason)

    prod_rate_reason = _rate_reason("Product", "products", prod_rate,
                                     thresholds.get("prod_rate_high"))
    if not product_cold and prod_rate_reason:
        reasons.append(prod_rate_reason)

    # --- how many returns, in total (50% of 2 orders tells you much less than
    # 50% of 200, so the actual numbers are given too) ---
    cust_returns = _get(row, "cust__returnsPerCustomer")
    if not customer_cold and _at_least(cust_returns, thresholds.get("cust_returns_high")):
        reasons.append(
            f"Customer has returned {_count(cust_returns, 'item', 'items')} historically "
            f"(top quartile of customers with history is "
            f"{thresholds['cust_returns_high']:,.0f}+)"
        )

    prod_returns = _get(row, "prod__returnsPerProduct")
    if not product_cold and _at_least(prod_returns, thresholds.get("prod_returns_high")):
        reasons.append(
            f"Product has been returned {_count(prod_returns, 'time', 'times')} historically "
            f"(top quartile of products with history is "
            f"{thresholds['prod_returns_high']:,.0f}+)"
        )

    # --- how much history there is ---
    if customer_cold:
        reasons.append(
            "New customer - no purchase history on file (cold-start fallback path)"
        )
    if product_cold:
        reasons.append(
            "New or rarely-seen product - limited historical data available"
        )

    cust_sales = _get(row, "cust__salesPerCustomer")
    if not customer_cold and _at_most(cust_sales, thresholds.get("cust_sales_low")):
        reasons.append(
            f"Thin customer history - only {_count(cust_sales, 'prior purchase', 'prior purchases')} on file "
            f"(bottom quartile), so the customer-side signal is weakly evidenced"
        )

    prod_sales = _get(row, "prod__salesPerProduct")
    if not product_cold and _at_most(prod_sales, thresholds.get("prod_sales_low")):
        reasons.append(
            f"Low-volume product - only {_count(prod_sales, 'prior sale', 'prior sales')} on file "
            f"(bottom quartile), so the product-side signal is weakly evidenced"
        )

    # --- price and discount ---
    discount = _get(row, "prod__avgDiscountValue")
    if not product_cold and _at_least(discount, thresholds.get("discount_high")):
        reasons.append(
            "Order involves a deep discount (top quartile of discount depth, "
            "computed from training data)"
        )

    price = _get(row, "prod__avgGbpPrice")
    if not product_cold and _at_least(price, thresholds.get("price_high")):
        reasons.append(
            f"Higher-value item (avg GBP {price:,.2f}, top quartile of priced products "
            f"starts at {thresholds['price_high']:,.2f}) - a return costs more to absorb"
        )

    # --- reasons the risk is LOW ---
    if not customer_cold and _at_most(cust_rate, thresholds.get("cust_rate_low")):
        mitigating.append(
            f"{MITIGATING_PREFIX}customer's historical return rate is low "
            f"({cust_rate:.0%}, bottom quartile of customers with history is at or below "
            f"{thresholds['cust_rate_low']:.0%})"
        )

    if not product_cold and _at_most(prod_rate, thresholds.get("prod_rate_low")):
        mitigating.append(
            f"{MITIGATING_PREFIX}product's historical return rate is low "
            f"({prod_rate:.0%}, bottom quartile of products with history is at or below "
            f"{thresholds['prod_rate_low']:.0%})"
        )

    if not reasons and not mitigating:
        if risk_score >= HIGH_RISK_SCORE_THRESHOLD:
            # The model learns from links between customers and products, so it
            # can rate an order risky for reasons no single rule here can spot.
            reasons.append(
                "Overall model-predicted risk is high, with no single named factor "
                "past its threshold - the signal is in the combination"
            )
        else:
            reasons.append("No significant individual risk factors identified for this order")

    return reasons + mitigating
