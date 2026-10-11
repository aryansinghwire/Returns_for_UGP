"""serving/tests/test_reasons.py - tests for the explanations shown next to
each order's score.

Staff use these explanations to decide what to do with an order. So the tests
focus on mistakes that would go unnoticed: treating a placeholder value as
real, a level of warning that can never appear, or a "low risk" note pushing a
real warning out of the "Top reason" spot.

Run from the main project folder:
    .venv/bin/python -m pytest serving/tests -q
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import HIGH_RETURN_RATE_THRESHOLD, HIGH_RISK_SCORE_THRESHOLD  # noqa: E402
from reasons import MITIGATING_PREFIX, compute_thresholds, derive_reasons  # noqa: E402

# Made to look like the real cut-offs: for products the top quarter starts
# below the fixed "high" level; for customers it starts above it.
THRESHOLDS = {
    "cust_rate_high": 0.71,
    "cust_rate_low": 0.29,
    "cust_returns_high": 10.0,
    "cust_sales_low": 6.0,
    "prod_rate_high": 0.38,
    "prod_rate_low": 0.10,
    "prod_returns_high": 153.0,
    "prod_sales_low": 294.0,
    "discount_high": 17.45,
    "price_high": 27.85,
}


def row(**overrides):
    """An ordinary order from a returning customer, with nothing unusual - so
    any explanation that appears in a test is one the test caused."""
    base = {
        "customer_no_history": 0,
        "product_no_history": 0,
        "cust__customerReturnRate": 0.45,
        "cust__returnsPerCustomer": 4.0,
        "cust__salesPerCustomer": 11.0,
        "prod__productReturnRate": 0.24,
        "prod__returnsPerProduct": 97.0,
        "prod__salesPerProduct": 460.0,
        "prod__avgDiscountValue": 16.4,
        "prod__avgGbpPrice": 18.7,
    }
    base.update(overrides)
    return base


def reasons_for(score=0.5, **overrides):
    return derive_reasons(row(**overrides), score, THRESHOLDS)


def test_unremarkable_order_says_so_rather_than_inventing_a_reason():
    assert reasons_for(score=0.3) == [
        "No significant individual risk factors identified for this order"
    ]


def test_high_score_with_no_named_factor_is_attributed_to_the_combination():
    out = reasons_for(score=HIGH_RISK_SCORE_THRESHOLD)
    assert len(out) == 1
    assert "no single named factor" in out[0]


@pytest.mark.parametrize("side,flag,field,value", [
    ("customer", "customer_no_history", "cust__customerReturnRate", 0.95),
    ("customer", "customer_no_history", "cust__returnsPerCustomer", 500.0),
    ("product", "product_no_history", "prod__productReturnRate", 0.95),
    ("product", "product_no_history", "prod__avgDiscountValue", 99.0),
    ("product", "product_no_history", "prod__avgGbpPrice", 999.0),
])
def test_no_history_placeholders_never_fire_a_threshold_rule(side, flag, field, value):
    """For a new customer or product, build_features.py fills in placeholder
    values. Treating those as real would tell staff "this customer returns 95%
    of orders" about someone the system has never seen."""
    out = derive_reasons(row(**{flag: 1, field: value}), 0.5, THRESHOLDS)
    cold_line = {
        "customer": "New customer - no purchase history on file (cold-start fallback path)",
        "product": "New or rarely-seen product - limited historical data available",
    }[side]
    assert cold_line in out
    # "New customer" (or product) is the only thing that side may say.
    assert not any(f"{value:.0f}" in r for r in out)


def test_return_rate_ladder_has_two_distinct_tiers_for_products():
    above_typical = reasons_for(prod__productReturnRate=0.40)[0]
    assert "above the typical range" in above_typical

    high = reasons_for(prod__productReturnRate=HIGH_RETURN_RATE_THRESHOLD)[0]
    assert "is high" in high


def test_relative_tier_is_suppressed_when_it_would_duplicate_the_absolute_one():
    """For customers, the top quarter starts at 0.71, which is already above
    the "high" level of 0.50. So the milder wording must never appear for
    customers."""
    for rate in [0.3, 0.49, 0.5, 0.72, 0.99]:
        out = derive_reasons(row(cust__customerReturnRate=rate), 0.5, THRESHOLDS)
        assert not any("Customer's historical return rate is above the typical range" in r
                       for r in out)


def test_volume_and_economics_rules_fire_on_their_own_columns():
    assert any("returned 25 items" in r for r in reasons_for(cust__returnsPerCustomer=25.0))
    assert any("returned 400 times" in r for r in reasons_for(prod__returnsPerProduct=400.0))
    assert any("Thin customer history" in r for r in reasons_for(cust__salesPerCustomer=3.0))
    assert any("Low-volume product" in r for r in reasons_for(prod__salesPerProduct=100.0))
    assert any("deep discount" in r for r in reasons_for(prod__avgDiscountValue=20.0))
    assert any("Higher-value item" in r for r in reasons_for(prod__avgGbpPrice=50.0))


def test_mitigating_factors_are_prefixed_and_never_lead():
    out = reasons_for(cust__customerReturnRate=0.05, prod__productReturnRate=0.02,
                      prod__avgGbpPrice=50.0)
    mitigating = [r for r in out if r.startswith(MITIGATING_PREFIX)]
    assert len(mitigating) == 2
    assert not out[0].startswith(MITIGATING_PREFIX), "a risk factor must hold the top-reason slot"
    assert out[-len(mitigating):] == mitigating


def test_a_clean_order_may_be_explained_entirely_by_mitigating_factors():
    out = reasons_for(score=0.05, cust__customerReturnRate=0.05, prod__productReturnRate=0.02)
    assert all(r.startswith(MITIGATING_PREFIX) for r in out)
    assert "No significant individual risk factors" not in " ".join(out)


def test_reasons_never_mention_the_undecodable_return_code_buckets():
    """The 13 lettered return-reason codes have no known meaning, and must
    never be mentioned - see the note at the top of reasons.py."""
    noisy = row(**{f"cust__customerId_level_return_code_{c}": 0.9 for c in "ABCDE"})
    noisy.update({f"prod__variantID_level_return_code_{c}": 0.9 for c in "ABCDE"})
    text = " ".join(derive_reasons(noisy, 0.9, THRESHOLDS))
    assert "return_code" not in text
    assert "return code" not in text.lower()


def test_reasons_never_key_off_age_or_gender():
    young = row(cust__age=18.0, cust__yearOfBirth=2008.0, cust__isMale=1.0, cust__premier=1.0)
    old = row(cust__age=72.0, cust__yearOfBirth=1954.0, cust__isMale=0.0, cust__premier=0.0)
    assert derive_reasons(young, 0.5, THRESHOLDS) == derive_reasons(old, 0.5, THRESHOLDS)


def test_thresholds_are_computed_only_over_rows_with_history():
    """A cut-off worked out from placeholder rows just gives back the
    placeholder value. Here 1,000 placeholder rows are all 0.5, and the 4 real
    rows must decide the cut-off instead."""
    train = pd.DataFrame({
        "cust__customerReturnRate": [0.5] * 1000 + [0.1, 0.2, 0.3, 0.4],
        "customer_no_history": [1] * 1000 + [0, 0, 0, 0],
        "product_no_history": [1] * 1004,
    })
    out = compute_thresholds(train)
    assert out["cust_rate_high"] == pytest.approx(0.325)
    assert out["cust_rate_low"] == pytest.approx(0.175)


def test_counts_are_pluralised():
    assert any("1 prior purchase on file" in r for r in reasons_for(cust__salesPerCustomer=1.0))
    assert any("3 prior purchases on file" in r for r in reasons_for(cust__salesPerCustomer=3.0))
    assert any("1 prior sale on file" in r for r in reasons_for(prod__salesPerProduct=1.0))
    assert any("returned 1 time historically" in r
               for r in derive_reasons(row(prod__returnsPerProduct=1.0), 0.5,
                                        {**THRESHOLDS, "prod_returns_high": 1.0}))
