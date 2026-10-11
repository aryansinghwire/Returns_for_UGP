"""
eval_harness.py - scores models, the same way every time.

Every model in the project - the simpler ones in train_baselines.py and the
graph models - uses this, so their results can be compared fairly.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
)


def compute_metrics(y_true, y_prob, threshold=0.5):
    """The standard scores: accuracy, precision, recall, F1, AUC and PR-AUC -
    the same ones the paper uses."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    y_pred = (y_prob >= threshold).astype(int)
    n_pos = int(y_true.sum())
    if n_pos == 0 or n_pos == len(y_true):
        return {"accuracy": accuracy_score(y_true, y_pred), "precision": None,
                "recall": None, "f1": None, "auc": None, "pr_auc": None,
                "n": len(y_true), "n_pos": n_pos,
                "note": "single-class slice - ranking metrics undefined"}
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "auc": roc_auc_score(y_true, y_prob),
        "pr_auc": average_precision_score(y_true, y_prob),
        "n": len(y_true),
        "n_pos": n_pos,
    }


def format_metrics(m, label=""):
    if m.get("precision") is None:
        return f"{label}: n={m['n']:,} ({m['n_pos']} positive) - {m.get('note', 'skipped')}"
    return (f"{label}: acc={m['accuracy']:.4f}  prec={m['precision']:.4f}  "
            f"rec={m['recall']:.4f}  f1={m['f1']:.4f}  "
            f"auc={m['auc']:.4f}  pr_auc={m['pr_auc']:.4f}  (n={m['n']:,})")


def high_return_slice_metrics(y_true, y_prob, customer_return_rate, threshold_rate=0.5):
    """Scores for customers who return a lot - those whose past return rate is
    at least threshold_rate. Repeats the paper's Table 4."""
    mask = np.asarray(customer_return_rate) >= threshold_rate
    if mask.sum() == 0:
        return None
    return compute_metrics(np.asarray(y_true)[mask], np.asarray(y_prob)[mask])


def cold_start_split_metrics(y_true, y_prob, no_history_flag):
    """Scores split into orders with real history and orders with none (new
    customers or new products). The paper doesn't report this, but it's the
    most important test here, because most real orders come from new
    customers."""
    flag = np.asarray(no_history_flag).astype(bool)
    y_true, y_prob = np.asarray(y_true), np.asarray(y_prob)
    out = {}
    if (~flag).sum() > 0:
        out["warm"] = compute_metrics(y_true[~flag], y_prob[~flag])
    if flag.sum() > 0:
        out["cold"] = compute_metrics(y_true[flag], y_prob[flag])
    return out


def leakage_probe(df, candidate_cols, label_col):
    """How well each single column predicts returns on its own, using its raw
    value as the score (no model needed).

    About 0.5 means it tells you nothing. A fairly high score (0.65 to 0.85) is
    normal for a genuinely useful column, like return rate. A score very close
    to 1.0 is the warning sign - it suggests the column accidentally contains
    information from the future it's meant to predict.

    This is something to read, not a pass/fail test. A useful column is
    supposed to predict well, so don't reject one just for scoring high.
    """
    y = df[label_col].values
    rows = []
    for c in candidate_cols:
        if c not in df.columns:
            continue
        try:
            auc = roc_auc_score(y, df[c].values)
        except Exception:
            continue
        rows.append((c, auc))
    rows.sort(key=lambda x: -x[1])
    return pd.DataFrame(rows, columns=["column", "single_feature_auc"])


def full_report(model_name, y_true, y_prob, customer_return_rate=None,
                 customer_no_history=None, product_no_history=None):
    """Run every score for one model and print the results."""
    print(f"\n{'=' * 60}\n{model_name}\n{'=' * 60}")
    overall = compute_metrics(y_true, y_prob)
    print(format_metrics(overall, "overall"))

    if customer_return_rate is not None:
        hr = high_return_slice_metrics(y_true, y_prob, customer_return_rate)
        if hr is not None:
            print(format_metrics(hr, "high-return customers (>=50%)"))

    if customer_no_history is not None:
        cs = cold_start_split_metrics(y_true, y_prob, customer_no_history)
        for k, m in cs.items():
            print(format_metrics(m, f"customer cold-start = {k}"))

    if product_no_history is not None:
        cs = cold_start_split_metrics(y_true, y_prob, product_no_history)
        for k, m in cs.items():
            print(format_metrics(m, f"product cold-start = {k}"))

    return overall
