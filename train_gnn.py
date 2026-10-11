#!/usr/bin/env python3
"""
Optional - train the GraphSAGE model and print its results.

This is the model the project uses. It's deliberately the simple one: a
standard building block from the PyTorch Geometric library, not written from
scratch. It learns from the links between customers and products, and is
compared against the four simpler models from train_baselines.py.

How it works:
  - two layers that let each customer learn from the products they bought, and
    each product learn from the customers who bought it
  - for each order, its customer and product are combined and passed through a
    small network that predicts how likely it is to be returned

It's scored with the same eval_harness as the simpler models, including the
split into new and returning customers, so the comparison is fair.

Run:
    python train_gnn.py /path/to/graph train
    python train_gnn.py /path/to/graph train_test
    python train_gnn.py /path/to/graph train_test /path/to/baseline_results.csv

The optional last argument is the baseline_results.csv that train_baselines.py
wrote FOR THE SAME DATA. If you give it, the script compares against those real
results. Without it, it prints no comparison at all - it never prints fixed
numbers that might not match your data.
"""

import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, to_hetero

from eval_harness import full_report

CONFIG = {
    "graph_dir": "./graph",
    "hidden_dim": 64,
    "epochs": 50,
    "lr": 0.005,
    "weight_decay": 5e-4,
    "seed": 42,
    "baseline_csv": None,  # optional: the simpler models' results, for the same data
}


def log(msg=""):
    print(msg)


class GNNEncoder(torch.nn.Module):
    """The two learning layers. The library copies them for each direction, so
    both customers and products are updated."""
    def __init__(self, hidden):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden)
        self.conv2 = SAGEConv((-1, -1), hidden)

    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        x = self.conv2(x, edge_index)
        return x


class EdgeDecoder(torch.nn.Module):
    """Combine an order's customer and product (plus any details about the
    order itself) and predict how likely it is to be returned. Order details are
    known even for new customers, so passing them in here lets this model see
    what the simpler models can see."""
    def __init__(self, hidden, edge_dim=0):
        super().__init__()
        self.edge_dim = edge_dim
        self.lin1 = torch.nn.Linear(2 * hidden + edge_dim, hidden)
        self.lin2 = torch.nn.Linear(hidden, 1)

    def forward(self, z_cust, z_prod, edge_index, edge_attr=None):
        row, col = edge_index
        parts = [z_cust[row], z_prod[col]]
        if self.edge_dim and edge_attr is not None:
            parts.append(edge_attr)
        h = torch.cat(parts, dim=-1)
        h = F.relu(self.lin1(h))
        return self.lin2(h).squeeze(-1)


class Model(torch.nn.Module):
    def __init__(self, metadata, hidden, edge_dim=0):
        super().__init__()
        self.encoder = to_hetero(GNNEncoder(hidden), metadata, aggr="sum")
        self.decoder = EdgeDecoder(hidden, edge_dim=edge_dim)

    def forward(self, x_dict, edge_index_dict, edge_label_index, edge_attr=None):
        z = self.encoder(x_dict, edge_index_dict)
        return self.decoder(z["customer"], z["product"], edge_label_index, edge_attr)


def load_baseline_comparison(csv_path):
    """Read the simpler models' results from train_baselines.py and return
    (the best model's name, its overall score) - or None if the file is
    missing or isn't in the expected format.

    It never crashes. If the file is missing or broken, the comparison is just
    skipped - it mustn't throw away a long training run that has already
    finished.
    """
    if not csv_path:
        return None
    if not os.path.exists(csv_path):
        log(f"\n(baseline_csv given but not found at {csv_path} - skipping comparison)")
        return None
    try:
        base = pd.read_csv(csv_path, index_col=0)
        if "auc" not in base.columns:
            log(f"\n(baseline_csv at {csv_path} has no 'auc' column - skipping "
                f"comparison; columns found: {list(base.columns)})")
            return None
        best_model = base["auc"].idxmax()
        best_auc = float(base["auc"].max())
        return best_model, best_auc
    except Exception as e:
        log(f"\n(couldn't read baseline_csv at {csv_path}: {type(e).__name__}: {e} "
            f"- skipping comparison)")
        return None


def main():
    if len(sys.argv) > 1:
        CONFIG["graph_dir"] = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "train"
    if len(sys.argv) > 3:
        CONFIG["baseline_csv"] = sys.argv[3]

    torch.manual_seed(CONFIG["seed"])
    np.random.seed(CONFIG["seed"])

    log("=" * 70)
    log(f"PHASE 2c - GraphSAGE  (mode={mode})")
    log("=" * 70)

    path = os.path.join(CONFIG["graph_dir"], f"graph_{mode}.pt")
    data = torch.load(path, weights_only=False)
    edge = data["customer", "buys", "product"]
    log(data)

    train_mask = edge.train_mask
    test_mask = edge.test_mask
    y = edge.edge_label

    # Details about each order, if build_graph.py added any. Split the same way
    # as the orders, into training and test.
    has_edge_attr = "edge_attr" in edge
    if has_edge_attr:
        edge_attr_all = edge.edge_attr
        edge_dim = edge_attr_all.size(1)
        names = getattr(edge, "edge_attr_names", None)
        log(f"using {edge_dim} per-order edge features"
            + (f": {list(names)}" if names is not None else ""))
        edge_attr_train = edge_attr_all[train_mask]
        edge_attr_test = edge_attr_all[test_mask]
    else:
        edge_dim = 0
        edge_attr_train = edge_attr_test = None
        log("no edge_attr on graph - GNN runs node-only. Expected on this "
            "data: the event table carries no order-level fields.")

    # The model only learns from TRAINING links. Letting it see the test links
    # would be cheating. Links go both ways, so customers and products are
    # both updated.
    mp_edge_index = edge.edge_index[:, train_mask]
    x_dict = {"customer": data["customer"].x, "product": data["product"].x}
    edge_index_dict = {
        ("customer", "buys", "product"): mp_edge_index,
        ("product", "rev_buys", "customer"): mp_edge_index.flip(0),
    }

    model = Model(data.metadata(), CONFIG["hidden_dim"], edge_dim=edge_dim)
    opt = torch.optim.Adam(model.parameters(), lr=CONFIG["lr"],
                           weight_decay=CONFIG["weight_decay"])

    train_ei = edge.edge_index[:, train_mask]
    test_ei = edge.edge_index[:, test_mask]
    y_train = y[train_mask]
    y_test = y[test_mask]

    # Returned and kept orders aren't quite equal in number, so weight them to
    # even that out (the same idea as in the simpler models).
    pos_weight = ((y_train == 0).sum() / (y_train == 1).sum().clamp(min=1)).clamp(0.2, 5.0)

    log(f"\ntraining {CONFIG['epochs']} epochs "
        f"({train_mask.sum().item():,} train edges, {test_mask.sum().item():,} test edges)")
    model.train()
    for ep in range(1, CONFIG["epochs"] + 1):
        opt.zero_grad()
        out = model(x_dict, edge_index_dict, train_ei, edge_attr_train)
        loss = F.binary_cross_entropy_with_logits(out, y_train, pos_weight=pos_weight)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()
        if ep % 5 == 0 or ep == 1:
            log(f"  epoch {ep:3d}  loss {loss.item():.4f}")

    # --- score the test orders ---
    model.eval()
    with torch.no_grad():
        test_logits = model(x_dict, edge_index_dict, test_ei, edge_attr_test)
        test_prob = torch.sigmoid(test_logits).numpy()

    y_test_np = y_test.numpy()
    cust_no_hist = edge.customer_no_history[test_mask].numpy() if "customer_no_history" in edge else None
    prod_no_hist = edge.product_no_history[test_mask].numpy() if "product_no_history" in edge else None
    cust_rr = edge.cust_return_rate[test_mask].numpy() if "cust_return_rate" in edge else None

    overall = full_report(f"GraphSAGE ({mode})", y_test_np, test_prob,
                          customer_return_rate=cust_rr,
                          customer_no_history=cust_no_hist,
                          product_no_history=prod_no_hist)

    # --- compare against the simpler models' real results, if given ---
    cmp = load_baseline_comparison(CONFIG["baseline_csv"])
    gnn_auc = overall.get("auc")
    if cmp is not None and gnn_auc is not None:
        best_model, best_auc = cmp
        delta = gnn_auc - best_auc
        log(f"\nBest Phase 1 tabular baseline on THIS dataset: "
            f"{best_model} overall auc={best_auc:.4f}")
        log(f"GraphSAGE overall auc={gnn_auc:.4f}  ({delta:+.4f} vs best baseline)")
        if delta <= 0:
            log("GraphSAGE did not beat the tabular baseline's OVERALL auc on this run.")
    else:
        log("\n(No baseline_csv given, or it couldn't be read - pass the path to "
            "THIS dataset's baseline_results.csv as a 3rd argument for a live "
            "comparison instead of eyeballing two separate printouts, e.g.:\n"
            "  python train_gnn.py data/graph train_test "
            "data/features/baseline_results.csv)")

    if mode == "train_test":
        log("\nThe customer cold-start = cold row above is the key number: compare "
            "it directly against the SAME row in your train_baselines.py output "
            "for this dataset (not any other run's numbers) to see whether graph "
            "structure helped on genuinely unseen customers.")


if __name__ == "__main__":
    main()