"""
serving/config.py - settings for building the dashboard's data file.

This is the ONLY place that decides what's real and what's made up. Anything
made up must be obviously fake (like the company names below) - never
something that could be mistaken for a real brand, date or order number.
"""

# --- where the input files are (from the main project folder) ---
GRAPH_DIR = "data/graph"
MODE = "train_test"
GRAPH_PATH = f"{GRAPH_DIR}/graph_{MODE}.pt"
SUB_TRAIN_PATH = f"{GRAPH_DIR}/sub_{MODE}_train.p"
SUB_TEST_PATH = f"{GRAPH_DIR}/sub_{MODE}_test.p"

# --- making the random parts repeatable ---
# The starting number for generating the made-up dates and companies, so they
# come out the same every time.
#
# The model's own settings are NOT here - export_seed.py reads them from
# train_gnn.CONFIG, so they're only written down once. This file must not
# import anything: the server reads PROTOTYPE_NOTICE from it, and the server
# doesn't have the machine-learning packages installed.
SEED = 42

# --- made-up details (NONE of these are in the real data) ---
# The test data covers October-November 2021, but it has no date for each
# order. So dates are spread evenly across that period, only so the dashboard
# has something to show over time.
#
# THIS IS NOT WHERE TRAINING AND TEST DATA ARE SPLIT, even though it looks like
# it. That split comes from the data files themselves - *_training.p and
# *_testing.p. Changing these dates only moves the made-up dates; it doesn't
# move a single real order between training and testing.
DATE_WINDOW = ("2021-10-01", "2021-11-30")

# Made-up company names for the demo. They must never look like the real
# brand codes in the data (Brand_A and so on) - those describe products, not
# the companies using the dashboard.
TENANT_NAMES = ["Aurora Apparel", "Nimbus Fashion Co.", "Solstice Trends"]
TENANT_WEIGHTS = [0.40, 0.35, 0.25]

ORDER_ID_PREFIX = "DEMO-ORD-"

# --- when to give each explanation ---
# Fixed cut-offs: a 50% return rate looks high to anyone, whatever the rest of
# the data looks like, so these two don't change with the data.
HIGH_RETURN_RATE_THRESHOLD = 0.5
HIGH_RISK_SCORE_THRESHOLD = 0.7
# For details with no natural "high" or "low" - price, number of orders,
# discount size - "high" means the top quarter and "low" the bottom quarter of
# the training data (only rows with real history). See reasons.THRESHOLD_SPEC.
HIGH_PERCENTILE = 0.75
LOW_PERCENTILE = 0.25

OUTPUT_PATH = "serving/output/orders_seed.json"

PROTOTYPE_NOTICE = (
    "PROTOTYPE - illustrative data. The underlying customer/product features and "
    "model risk score are real (scored by the trained GraphSAGE model on real "
    "ASOS UK fashion return data), but order id, order date, and tenant/brand "
    "are synthesized for this demo: the dataset has no real order id, no "
    "per-order timestamp, and no multi-brand tenant structure. This is a "
    "historical-return-prediction dataset being replayed as a live returns-risk "
    "queue for demonstration only - not a real-world returns accuracy claim."
)
