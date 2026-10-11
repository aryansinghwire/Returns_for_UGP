#!/usr/bin/env python3
"""
Step 2 - prepare the model's inputs.

Takes the cleaned data from clean_data.py and makes one row per order: whether
it was returned, plus everything known about its customer and its product.
The four simpler comparison models are trained on this table.

It deals with two facts about the data:
  - For about 5% of orders the customer has no record, and for about a third
    the product has none. These orders are kept and given default values, not
    thrown away - they're real orders from new customers or new products, and
    those need scoring most of all.
  - About 78% of customers in the test data never appear in the training data.
    A "no history" flag is added for customers and products, so the models can
    tell made-up default values from real history.

How missing values are filled in, by kind of column:
  - return rates (*ReturnRate)                -> the average rate
  - counts and return-reason shares           -> 0 (no history means none)
    (salesPer*, returnsPer*, *_return_code_*)
  - other measurements                        -> the average (0 wouldn't make
    (age, avgGbpPrice, avgDiscountValue)          sense for these)
  - yes/no columns (Country_*, Brand_*,       -> 0 (no category ticked)
    productType_*, isMale, premier)
  - text columns (e.g. shippingCountry)       -> removed (the yes/no columns
                                                  already hold the same thing)

Run:
    python build_features.py /path/to/clean /path/to/features_out
"""

import os
import sys

import numpy as np
import pandas as pd

CONFIG = {
    "clean_dir": ".",
    "out_dir": "./features",
    "files": {
        "event_train":    "event_table_training.p",
        "event_test":     "event_table_testing.p",
        "customer_train": "customer_nodes_training.p",
        "customer_test":  "customer_nodes_testing.p",
        "product_train":  "product_nodes_training.p",
        "product_test":   "product_nodes_testing.p",
    },
    "customer_key": "hash(customerId)",
    "product_key": "hash(variantID)",
    "label_col": "isReturned",
    "rate_patterns": ["returnrate"],
    "count_patterns": ["salesper", "returnsper", "level_return_code", "_return_code_"],
    "continuous_patterns": ["age", "avggbpprice", "avgdiscountvalue"],
    # Any other number column is filled with 0, like a yes/no column.
}


def log(msg=""):
    print(msg)


def classify_columns(cols, cfg):
    """Sort the columns by how their missing values should be filled in,
    based on their names. Returns {rule name: [columns]}."""
    rate, count, cont, other = [], [], [], []
    for c in cols:
        lc = c.lower()
        if any(p in lc for p in cfg["rate_patterns"]):
            rate.append(c)
        elif any(p in lc for p in cfg["count_patterns"]):
            count.append(c)
        elif any(p in lc for p in cfg["continuous_patterns"]):
            cont.append(c)
        else:
            other.append(c)
    return {"rate": rate, "count": count, "continuous": cont, "binary_other": other}


def prep_node_table(df, key_col, cfg, table_label):
    """Keep only the number columns (listing any others it removes), and work
    out each column's fill-in value. Returns (the table, the fill-in values)."""
    obj_cols = [c for c in df.columns if df[c].dtype == "object" and c != key_col]
    if obj_cols:
        log(f"  {table_label}: dropping non-numeric column(s) {obj_cols} "
            f"(one-hot equivalents are kept)")
    feat_cols = [c for c in df.columns
                 if c != key_col and c not in obj_cols
                 and pd.api.types.is_numeric_dtype(df[c])]
    df_num = df[[key_col] + feat_cols].copy()

    buckets = classify_columns(feat_cols, cfg)
    impute = {}
    for c in buckets["rate"] + buckets["continuous"]:
        impute[c] = float(df_num[c].mean())
    for c in buckets["count"] + buckets["binary_other"]:
        impute[c] = 0.0

    log(f"  {table_label}: {len(feat_cols)} numeric features "
        f"(rate={len(buckets['rate'])}, count/reason={len(buckets['count'])}, "
        f"continuous={len(buckets['continuous'])}, binary/other={len(buckets['binary_other'])})")
    return df_num, feat_cols, impute


def build_split(event_df, cust_df, prod_df, cfg, split_name):
    ck, pk, label = cfg["customer_key"], cfg["product_key"], cfg["label_col"]

    log(f"\n--- building {split_name} ---")
    cust_num, cust_feats, cust_impute = prep_node_table(cust_df, ck, cfg, "customer")
    prod_num, prod_feats, prod_impute = prep_node_table(prod_df, pk, cfg, "product")

    # Start customer columns with cust__ and product ones with prod__, so
    # columns with the same name never clash.
    cust_num = cust_num.rename(columns={c: f"cust__{c}" for c in cust_feats})
    prod_num = prod_num.rename(columns={c: f"prod__{c}" for c in prod_feats})
    cust_impute = {f"cust__{k}": v for k, v in cust_impute.items()}
    prod_impute = {f"prod__{k}": v for k, v in prod_impute.items()}

    df = event_df.merge(cust_num, on=ck, how="left")
    df = df.merge(prod_num, on=pk, how="left")

    cust_cols = list(cust_impute.keys())
    prod_cols = list(prod_impute.keys())

    df["customer_no_history"] = df[cust_cols[0]].isna().astype(np.int8) if cust_cols else 0
    df["product_no_history"] = df[prod_cols[0]].isna().astype(np.int8) if prod_cols else 0

    n_cust_orphan = int(df["customer_no_history"].sum())
    n_prod_orphan = int(df["product_no_history"].sum())
    log(f"  imputed {n_cust_orphan:,} customer-side orphans "
        f"({100 * n_cust_orphan / len(df):.2f}%), "
        f"{n_prod_orphan:,} product-side orphans "
        f"({100 * n_prod_orphan / len(df):.2f}%)")

    df = df.fillna({**cust_impute, **prod_impute})

    # Use smaller number types - this halves the memory needed.
    num_cols = cust_cols + prod_cols
    df[num_cols] = df[num_cols].astype(np.float32)

    log(f"  final shape: {df.shape[0]:,} rows x {df.shape[1]} cols "
        f"({df.memory_usage(deep=True).sum() / 1e6:.1f} MB)")
    return df


def main():
    if len(sys.argv) > 1:
        CONFIG["clean_dir"] = sys.argv[1]
    if len(sys.argv) > 2:
        CONFIG["out_dir"] = sys.argv[2]

    clean, out = CONFIG["clean_dir"], CONFIG["out_dir"]
    os.makedirs(out, exist_ok=True)
    log("=" * 70)
    log("PHASE 1 - FEATURE BUILD")
    log(f"clean: {os.path.abspath(clean)}")
    log(f"out  : {os.path.abspath(out)}")
    log("=" * 70)

    def load(name):
        return pd.read_pickle(os.path.join(clean, CONFIG["files"][name]))

    ev_tr, ev_te = load("event_train"), load("event_test")
    cust_tr, cust_te = load("customer_train"), load("customer_test")
    prod_tr, prod_te = load("product_train"), load("product_test")

    train_feats = build_split(ev_tr, cust_tr, prod_tr, CONFIG, "train")
    test_feats = build_split(ev_te, cust_te, prod_te, CONFIG, "test")

    train_feats.to_pickle(os.path.join(out, "train_features.p"))
    test_feats.to_pickle(os.path.join(out, "test_features.p"))

    log("\n" + "=" * 70)
    log("DONE. Feature tables written to the output folder.")
    log("Next: run train_baselines.py against this folder.")
    log("=" * 70)


if __name__ == "__main__":
    main()