#!/usr/bin/env python3
"""
Step 4 - link each customer to the products they bought.

Turns the sample from sample_subgraph.py into a network the model can learn
from, using the PyTorch Geometric library:

  - one point for each customer, holding that customer's details (cust__*)
  - one point for each product, holding that product's details (prod__*)
  - one link for each order, between its customer and its product, marked
    returned or kept
  - a record of which links are for training and which for testing, so one
    network holds both

Customers and products are stored as two different kinds of point, because
they have different details - as in the paper. Their details come straight
from step 2, one row per customer or product.

Run:
    python build_graph.py /path/to/graph train
    python build_graph.py /path/to/graph train_test
"""

import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch_geometric.data import HeteroData

CONFIG = {
    "graph_dir": "./graph",
    "customer_key": "hash(customerId)",
    "product_key": "hash(variantID)",
    "label_col": "isReturned",
}


def log(msg=""):
    print(msg)


def node_feature_frame(edges_all, key, prefix):
    """One row of details per customer (or product). Their details are the
    same on every order, so the first row for each is used."""
    feat_cols = [c for c in edges_all.columns if c.startswith(prefix)]
    per_node = edges_all.drop_duplicates(subset=[key])[[key] + feat_cols]
    return per_node.reset_index(drop=True), feat_cols


def main():
    if len(sys.argv) > 1:
        CONFIG["graph_dir"] = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "train"

    ck, pk, lab = CONFIG["customer_key"], CONFIG["product_key"], CONFIG["label_col"]
    gdir = CONFIG["graph_dir"]

    log("=" * 70)
    log(f"PHASE 2b - BUILD PyG GRAPH  (mode={mode})")
    log("=" * 70)

    tr = pd.read_pickle(os.path.join(gdir, f"sub_{mode}_train.p"))
    te = pd.read_pickle(os.path.join(gdir, f"sub_{mode}_test.p"))
    tr["_is_test"] = 0
    te["_is_test"] = 1
    alle = pd.concat([tr, te], ignore_index=True)
    log(f"train edges {len(tr):,}, test edges {len(te):,}, total {len(alle):,}")

    # --- give every customer and product a number, across training and test ---
    cust_feats_df, cust_cols = node_feature_frame(alle, ck, "cust__")
    prod_feats_df, prod_cols = node_feature_frame(alle, pk, "prod__")

    cust_ids = cust_feats_df[ck].to_numpy()
    prod_ids = prod_feats_df[pk].to_numpy()
    cust_index = {cid: i for i, cid in enumerate(cust_ids)}
    prod_index = {pid: i for i, pid in enumerate(prod_ids)}
    log(f"nodes: {len(cust_ids):,} customers ({len(cust_cols)} feats), "
        f"{len(prod_ids):,} products ({len(prod_cols)} feats)")

    # --- put every detail on the same scale ---
    # This kind of model is thrown off by numbers of very different sizes -
    # prices up to about 518 next to sales counts up to about 3,000. So each
    # detail is rescaled to a similar range. The scaling is worked out from
    # training data only, so the test data doesn't leak into it.
    train_edges = alle[alle["_is_test"] == 0]
    train_cust_ids = set(train_edges[ck].unique())
    train_prod_ids = set(train_edges[pk].unique())

    cust_train_rows = cust_feats_df[ck].isin(train_cust_ids).to_numpy()
    prod_train_rows = prod_feats_df[pk].isin(train_prod_ids).to_numpy()

    cust_scaler = StandardScaler().fit(cust_feats_df.loc[cust_train_rows, cust_cols].to_numpy(np.float32))
    prod_scaler = StandardScaler().fit(prod_feats_df.loc[prod_train_rows, prod_cols].to_numpy(np.float32))

    x_cust = torch.tensor(cust_scaler.transform(cust_feats_df[cust_cols].to_numpy(np.float32)), dtype=torch.float32)
    x_prod = torch.tensor(prod_scaler.transform(prod_feats_df[prod_cols].to_numpy(np.float32)), dtype=torch.float32)

    # --- the links (customer to product), whether each was returned, and
    # which are for training or testing ---
    src = alle[ck].map(cust_index).to_numpy()
    dst = alle[pk].map(prod_index).to_numpy()
    edge_index = torch.tensor(np.vstack([src, dst]), dtype=torch.long)
    edge_label = torch.tensor(alle[lab].to_numpy(np.float32))
    is_test = alle["_is_test"].to_numpy().astype(bool)
    train_mask = torch.tensor(~is_test)
    test_mask = torch.tensor(is_test)

    data = HeteroData()
    data["customer"].x = x_cust
    data["product"].x = x_prod
    data["customer", "buys", "product"].edge_index = edge_index
    data["customer", "buys", "product"].edge_label = edge_label
    data["customer", "buys", "product"].train_mask = train_mask
    data["customer", "buys", "product"].test_mask = test_mask
    # Add links in the other direction too (product to customer), so the model
    # learns about products as well as customers. Without them, products would
    # never be updated, and the library refuses to build the model.
    data["product", "rev_buys", "customer"].edge_index = edge_index.flip(0)

    # --- details about each ORDER itself (ord__* columns) ---------------------
    # Details about the order itself (like payment type) are known even for a
    # brand-new customer - exactly where customer history can't help. They're
    # attached to each link and given straight to the final prediction.
    #
    # None exist today - the order table here only has three columns. This is
    # kept because a different dataset would have them, and this is how they
    # would reach the model.
    ord_cols = sorted([c for c in alle.columns if c.startswith("ord__")])
    if ord_cols:
        edge_attr = torch.tensor(alle[ord_cols].to_numpy(np.float32), dtype=torch.float32)
        data["customer", "buys", "product"].edge_attr = edge_attr
        data["customer", "buys", "product"].edge_attr_names = ord_cols
        log(f"edge features: {len(ord_cols)} ord__ columns attached to edges")
    else:
        log("edge features: none found (no ord__ columns) - GNN runs node-only")

    # Keep the new-customer and new-product flags, and return rate, for scoring later.
    for meta in ("customer_no_history", "product_no_history"):
        if meta in alle.columns:
            data["customer", "buys", "product"][meta] = torch.tensor(
                alle[meta].to_numpy(np.float32))
    rr_col = next((c for c in cust_cols if c.lower() == "cust__customerreturnrate"), None)
    if rr_col:
        data["customer", "buys", "product"]["cust_return_rate"] = torch.tensor(
            alle[rr_col].to_numpy(np.float32))

    out = os.path.join(gdir, f"graph_{mode}.pt")
    torch.save(data, out)
    log(f"\nsaved PyG graph to {out}")
    log(data)
    log("Next: train_gnn.py to train GraphSAGE on this graph.")


if __name__ == "__main__":
    main()
