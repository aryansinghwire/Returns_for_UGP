"""
serving/synth.py - makes up the details the real data doesn't have: order
numbers, order dates and companies. They come out the same every time, and
they're all obviously fake (see config.PROTOTYPE_NOTICE).
"""

import numpy as np
import pandas as pd

from config import DATE_WINDOW, ORDER_ID_PREFIX, TENANT_NAMES, TENANT_WEIGHTS


def make_order_ids(n):
    return [f"{ORDER_ID_PREFIX}{i + 1:06d}" for i in range(n)]


def make_order_dates(n, seed, window=DATE_WINDOW):
    """Random dates spread evenly across October-November 2021, the period the
    test data covers. The data has no real order dates - this is only so the
    dashboard has something to show over time."""
    start = pd.Timestamp(window[0])
    end = pd.Timestamp(window[1])
    span_days = (end - start).days
    rng = np.random.RandomState(seed)
    offsets = rng.uniform(0, span_days, size=n)
    dates = [(start + pd.Timedelta(days=float(o))).strftime("%Y-%m-%d") for o in offsets]
    return dates


def assign_tenants(customer_ids, seed, names=TENANT_NAMES, weights=TENANT_WEIGHTS):
    """Gives each order a made-up company. It's decided per CUSTOMER, so all of
    one customer's orders go to the same company - like a real customer, who
    shops at one store rather than a random one each time."""
    customer_ids = pd.Series(customer_ids).astype(str)
    unique_customers = customer_ids.unique()
    rng = np.random.RandomState(seed)
    tenant_per_customer = rng.choice(names, size=len(unique_customers), p=weights)
    mapping = dict(zip(unique_customers, tenant_per_customer))
    return customer_ids.map(mapping).to_numpy()
