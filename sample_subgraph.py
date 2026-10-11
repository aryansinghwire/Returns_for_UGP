#!/usr/bin/env python3
"""
Step 3 - take a small, connected sample of customers and products.

The full data has about 1.34 million orders. This takes a much smaller sample
to work with. Keeping it small means the whole thing fits in memory at once -
which also means one of the paper's parts (GEA, which links up separate pieces
of a very large dataset) isn't needed.

What matters most is that the sample is CONNECTED - customers have to share
products with each other. A random sample would scatter into pieces where
almost no customer shares a product with another, leaving the model nothing to
learn from. So the sample grows outward from a starting set of popular
products, following which customers bought them.

Two modes:
  - "train"      : only uses training orders, so every customer has been seen
                   before. Used to check everything works.
  - "train_test" : takes a sample, then keeps training orders (Sep-Oct) and test
                   orders (Oct-Nov) apart. Test customers the model has never
                   seen stay in, so this tests the real situation.

Run:
    python sample_subgraph.py /path/to/features /path/to/graph_out train 20000
    python sample_subgraph.py /path/to/features /path/to/graph_out train_test 20000

The last number is a TARGET number of orders, and sampling stops as soon as it
reaches it. So a bigger number doesn't make the sample grow smoothly - it can
overshoot by ten times or more. 20000 gives the sample this project reports:
400 products, 35,348 customers, 36,114 orders, split 19,868 for training and
16,246 for testing. (These examples used to say 40000, which gives about twenty
times as many orders and no longer matches what serving/export_seed.py expects.)
"""

import os
import sys

import numpy as np
import pandas as pd

CONFIG = {
    "features_dir": "./features",
    "out_dir": "./graph",
    "customer_key": "hash(customerId)",
    "product_key": "hash(variantID)",
    "label_col": "isReturned",
    "seed": 42,
    # Sampling starts from the most popular products, so the sample is well
    # connected rather than scattered into tiny pieces.
    #
    # The sample's size is set by two things: this number, and the target given
    # on the command line (20000 in this project's runs). Changing either changes
    # everything after it, and serving/export_seed.py warns you if the number of
    # test orders is no longer 16,246.
    "n_seed_products": 400,
}


def log(msg=""):
    print(msg)


def load_features(features_dir, name):
    return pd.read_pickle(os.path.join(features_dir, f"{name}_features.p"))


def grow_connected_sample(events, cfg, target_events, seed_pool_events=None):
    """
    Grow a connected sample. Start from some popular products, take all their
    orders, find the customers who placed them, take those customers' other
    orders too, and repeat until there are about target_events orders. Growing
    outward like this keeps the sample connected.

    seed_pool_events (optional) is used to PICK the starting products, while
    events is where orders are actually taken from. In "train" mode they're the
    same; in "train_test" mode they differ.
    """
    ck, pk = cfg["customer_key"], cfg["product_key"]
    rng = np.random.RandomState(cfg["seed"])
    pool = events if seed_pool_events is None else seed_pool_events

    # Pick the starting products: popular ones, so the sample is well connected.
    prod_degree = pool[pk].value_counts()
    top_products = prod_degree.head(cfg["n_seed_products"] * 5).index.to_numpy()
    seed_products = set(rng.choice(top_products,
                                   size=min(cfg["n_seed_products"], len(top_products)),
                                   replace=False))

    chosen_products = set(seed_products)
    chosen_customers = set()
    frontier_products = set(seed_products)

    while True:
        # Orders for the products just added.
        mask = events[pk].isin(frontier_products)
        new_customers = set(events.loc[mask, ck].unique()) - chosen_customers
        chosen_customers |= new_customers
        if not new_customers:
            break

        # Those customers' other orders bring in more products.
        cmask = events[ck].isin(new_customers)
        # NOTE: this count must use the same rule as the final sample below (an
        # order is kept only if BOTH its customer AND its product were chosen).
        # Counting orders where EITHER was chosen gives too big a number, so the
        # loop could think it had hit the target and stop too early - leaving a
        # final sample far smaller than asked for. Using the same rule keeps the
        # count honest about what will really be kept.
        current_edges = int(events[events[pk].isin(chosen_products)
                                   & events[ck].isin(chosen_customers)].shape[0])
        if current_edges >= target_events:
            break

        new_products = set(events.loc[cmask, pk].unique()) - chosen_products
        chosen_products |= new_products
        frontier_products = new_products
        if not new_products:
            break

    sub = events[events[pk].isin(chosen_products) & events[ck].isin(chosen_customers)]
    return sub.reset_index(drop=True)


def summarize(sub, cfg, label):
    ck, pk, lab = cfg["customer_key"], cfg["product_key"], cfg["label_col"]
    log(f"  {label}: {len(sub):,} edges, "
        f"{sub[ck].nunique():,} customers, {sub[pk].nunique():,} products, "
        f"return rate {sub[lab].mean():.3f}")


def main():
    if len(sys.argv) > 1:
        CONFIG["features_dir"] = sys.argv[1]
    if len(sys.argv) > 2:
        CONFIG["out_dir"] = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "train"
    # 20000, not 40000. Sampling stops once it reaches the target, so a bigger
    # number doesn't grow the result smoothly. 20000 gives the sample this
    # project reports; 40000 gives about twenty times as many orders, and no
    # longer matches the 16,246 test orders serving/export_seed.py expects.
    target = int(sys.argv[4]) if len(sys.argv) > 4 else 20000

    os.makedirs(CONFIG["out_dir"], exist_ok=True)
    log("=" * 70)
    log(f"PHASE 2a - SUBGRAPH SAMPLER  (mode={mode}, target~{target:,} train edges)")
    log("=" * 70)

    ck, pk = CONFIG["customer_key"], CONFIG["product_key"]

    if mode == "train":
        train = load_features(CONFIG["features_dir"], "train")
        log(f"loaded train features: {train.shape}")
        sub = grow_connected_sample(train, CONFIG, target)
        summarize(sub, CONFIG, "sampled subgraph")

        # Set aside 20% of the orders for testing.
        rng = np.random.RandomState(CONFIG["seed"])
        perm = rng.permutation(len(sub))
        n_test = int(len(sub) * 0.2)
        test_idx, train_idx = perm[:n_test], perm[n_test:]
        sub_train = sub.iloc[train_idx].reset_index(drop=True)
        sub_test = sub.iloc[test_idx].reset_index(drop=True)
        summarize(sub_train, CONFIG, "  -> train split")
        summarize(sub_test, CONFIG, "  -> test  split")

    elif mode == "train_test":
        train = load_features(CONFIG["features_dir"], "train")
        test = load_features(CONFIG["features_dir"], "test")
        log(f"loaded train {train.shape}, test {test.shape}")

        # Sample from training and test orders together, starting from training ones.
        combined = pd.concat([train.assign(_split="train"),
                              test.assign(_split="test")], ignore_index=True)
        sub = grow_connected_sample(combined, CONFIG, target, seed_pool_events=train)
        sub_train = sub[sub["_split"] == "train"].drop(columns="_split").reset_index(drop=True)
        sub_test = sub[sub["_split"] == "test"].drop(columns="_split").reset_index(drop=True)

        summarize(sub, CONFIG, "sampled subgraph (combined)")
        summarize(sub_train, CONFIG, "  -> train edges (Sep-Oct)")
        summarize(sub_test, CONFIG, "  -> test  edges (Oct-Nov)")

        # Report how many test customers and products never appear in training.
        tr_cust, tr_prod = set(sub_train[ck]), set(sub_train[pk])
        te_cust, te_prod = set(sub_test[ck]), set(sub_test[pk])
        cold_c = len(te_cust - tr_cust)
        cold_p = len(te_prod - tr_prod)
        log(f"  cold-start in subgraph: "
            f"{cold_c:,}/{len(te_cust):,} test customers unseen "
            f"({100*cold_c/max(len(te_cust),1):.1f}%), "
            f"{cold_p:,}/{len(te_prod):,} test products unseen "
            f"({100*cold_p/max(len(te_prod),1):.1f}%)")
    else:
        log(f"unknown mode '{mode}' - use 'train' or 'train_test'")
        return

    sub_train.to_pickle(os.path.join(CONFIG["out_dir"], f"sub_{mode}_train.p"))
    sub_test.to_pickle(os.path.join(CONFIG["out_dir"], f"sub_{mode}_test.p"))
    log(f"\nwrote sub_{mode}_train.p and sub_{mode}_test.p to {CONFIG['out_dir']}")
    log("Next: build_graph.py to convert these into a PyG graph object.")


if __name__ == "__main__":
    main()