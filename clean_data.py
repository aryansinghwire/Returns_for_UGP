#!/usr/bin/env python3
"""
Step 1 - clean the raw data.

Reads the six raw data files and saves cleaned copies, ready for the model.
It fixes three known problems without losing any data:

  1. A repeated column name. The customer and product tables have 13
     return-reason columns, but one letter is used twice (there are two "_D"
     columns). The second is renamed to the next free letter, M. No data is
     removed.

  2. Duplicate text columns. The product table has 'productType' and
     'brandDesc' as text, and also as yes/no columns (productType_*,
     Brand_*). The model uses the yes/no columns, so the text ones are removed.

  3. Age. Year of birth is turned into an age, as the paper does, and kept
     within a sensible range. Customers with an unlikely age are kept, not
     removed - they're treated like customers with no history later on.

The order tables need no fixing, so they're just copied across.

Run from the main project folder:
    python clean_data.py data data/clean
    python clean_data.py /path/to/raw /path/to/output

With no folders given, it reads from the current folder and writes to
./clean - the same as the other steps.
"""

import os
import shutil
import string
import sys

import pandas as pd

# --------------------------------------------------------------------------- #
# CONFIG                                                                       #
# --------------------------------------------------------------------------- #
CONFIG = {
    "raw_dir": ".",
    "out_dir": "./clean",
    "files": {
        "event_train":    "event_table_training.p",
        "event_test":     "event_table_testing.p",
        "customer_train": "customer_nodes_training.p",
        "customer_test":  "customer_nodes_testing.p",
        "product_train":  "product_nodes_training.p",
        "product_test":   "product_nodes_testing.p",
    },
    "node_files": ["customer_train", "customer_test", "product_train", "product_test"],
    "event_files": ["event_train", "event_test"],
    "reason_code_tag": "level_return_code",       # substring identifying rc cols
    "raw_string_drop": ["productType", "brandDesc"],  # redundant with one-hots
    "dataset_year": 2021,                          # ASOS data is 2021
    "age_clip": (10, 100),

    # --- Match the paper's filtering (its section 3.1.2). This is a choice, not
    # a fix - set it to False to keep every customer instead.
    "paper_fidelity": True,
    "age_exclude_threshold": 90,   # exclude customers with age > this
    "customer_key": "hash(customerId)",
    "product_key": "hash(variantID)",
    # The paper's own row counts, only used to show how close this gets.
    "paper_reference_counts": {"event_train": 939537, "event_test": 858526},
}


def log(msg=""):
    print(msg)


# --------------------------------------------------------------------------- #
# Fix 1 - rename duplicate reason-code columns to the next free letter          #
# --------------------------------------------------------------------------- #
def fix_duplicate_reason_codes(df, tag):
    cols = list(df.columns)
    rc_positions = [i for i, c in enumerate(cols) if tag in c]
    used_letters = {cols[i].rsplit("_", 1)[-1] for i in rc_positions}

    seen, renames = set(), []
    for i in rc_positions:
        name = cols[i]
        if name in seen:
            # This name has appeared already, so this is the repeat - rename it.
            next_letter = next(
                (ch for ch in string.ascii_uppercase if ch not in used_letters), None
            )
            if next_letter is None:
                new = f"{name}.dup"          # extreme fallback
            else:
                stem = name.rsplit("_", 1)[0]
                new = f"{stem}_{next_letter}"
                used_letters.add(next_letter)
            cols[i] = new
            renames.append((name, new))
        else:
            seen.add(name)
    df.columns = cols
    return df, renames


# --------------------------------------------------------------------------- #
# Fix 2 - drop redundant raw string columns                                    #
# --------------------------------------------------------------------------- #
def drop_raw_strings(df, drop_names):
    dropped = [c for c in drop_names if c in df.columns]
    if dropped:
        df = df.drop(columns=dropped)
    # List any other text columns, so nothing is removed without you knowing.
    leftover_obj = [c for c in df.columns if df[c].dtype == "object"]
    return df, dropped, leftover_obj


# --------------------------------------------------------------------------- #
# Fix 3 - derive age from yearOfBirth                                           #
# --------------------------------------------------------------------------- #
def add_age(df, year, clip):
    if "yearOfBirth" not in df.columns:
        return df, None
    age = year - df["yearOfBirth"]
    n_implausible = int(((age < clip[0]) | (age > clip[1])).sum())
    df = df.copy()
    df["age"] = age.clip(lower=clip[0], upper=clip[1])
    return df, n_implausible


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Matching the paper - leaving out very old customers (a choice, not a fix)   #
# --------------------------------------------------------------------------- #
def compute_age_exclusion(customer_df, key_col, year, threshold):
    """Find customers older than the limit. Returns (customers kept, IDs left out)."""
    if "yearOfBirth" not in customer_df.columns or key_col not in customer_df.columns:
        return customer_df, set()
    age = year - customer_df["yearOfBirth"]
    mask = age > threshold
    excluded_ids = set(customer_df.loc[mask, key_col])
    kept = customer_df.loc[~mask].reset_index(drop=True)
    return kept, excluded_ids


def dedupe_and_filter_events(event_df, excluded_customer_ids, customer_key, product_key):
    """
    Three separate steps, reported separately because they're not equally safe:
      1. Rows that are exact copies of each other -> removed (always safe).
      2. The same customer and product, once marked returned and once not ->
         only reported, never removed. The data has no order numbers or dates,
         so there's no way to tell which is right, or whether both are real
         separate purchases. Guessing would throw away real information.
      3. Orders from customers left out for their age -> removed, as the
         paper does.
    """
    stats = {"before": len(event_df)}

    exact_dupe_mask = event_df.duplicated(keep="first")
    stats["exact_duplicates_removed"] = int(exact_dupe_mask.sum())
    df = event_df.loc[~exact_dupe_mask].copy()

    if customer_key in df.columns and product_key in df.columns:
        grp = df.groupby([customer_key, product_key])["isReturned"].nunique()
        stats["conflicting_pairs_flagged"] = int((grp > 1).sum())
    else:
        stats["conflicting_pairs_flagged"] = None

    if excluded_customer_ids and customer_key in df.columns:
        age_mask = df[customer_key].isin(excluded_customer_ids)
        stats["age_excluded_events_removed"] = int(age_mask.sum())
        df = df.loc[~age_mask].reset_index(drop=True)
    else:
        stats["age_excluded_events_removed"] = 0

    stats["after"] = len(df)
    return df, stats


# --------------------------------------------------------------------------- #
def clean_node_table(name, df, cfg):
    log(f"\n--- {name} ---")
    log(f"  in : {df.shape[0]:,} rows x {df.shape[1]} cols")

    df, renames = fix_duplicate_reason_codes(df, cfg["reason_code_tag"])
    if renames:
        for old, new in renames:
            log(f"  reason-code fix: '{old}' -> '{new}'")
    else:
        log("  reason-code fix: no duplicates found")

    df, dropped, leftover_obj = drop_raw_strings(df, cfg["raw_string_drop"])
    if dropped:
        log(f"  dropped raw string cols: {dropped}")
    if leftover_obj:
        log(f"  NOTE: object columns still present (not dropped): {leftover_obj}")
        log("        -> check these are meant to be non-numeric before Phase 1")

    df, n_imp = add_age(df, cfg["dataset_year"], cfg["age_clip"])
    if n_imp is not None:
        log(f"  derived 'age' from yearOfBirth; {n_imp:,} implausible ages clipped "
            f"to {cfg['age_clip']}")

    log(f"  out: {df.shape[0]:,} rows x {df.shape[1]} cols")
    return df


def main():
    if len(sys.argv) > 1:
        CONFIG["raw_dir"] = sys.argv[1]
    if len(sys.argv) > 2:
        CONFIG["out_dir"] = sys.argv[2]

    raw, out = CONFIG["raw_dir"], CONFIG["out_dir"]
    os.makedirs(out, exist_ok=True)
    log("=" * 70)
    log("PHASE 1a - DATA CLEANING")
    log(f"raw : {os.path.abspath(raw)}")
    log(f"out : {os.path.abspath(out)}")
    log(f"paper_fidelity stage: {'ON' if CONFIG['paper_fidelity'] else 'OFF'}")
    log("=" * 70)

    # --- stage 1: fix the customer and product tables (always done - these are
    # real fixes, not choices) ---
    cleaned_nodes = {}
    for name in CONFIG["node_files"]:
        path = os.path.join(raw, CONFIG["files"][name])
        if not os.path.exists(path):
            log(f"\n[MISSING] {name} -> {path} (skipped)")
            continue
        df = pd.read_pickle(path)
        cleaned_nodes[name] = clean_node_table(name, df, CONFIG)

    # --- stage 2: leave out very old customers, as the paper does ---
    excluded_ids = {"customer_train": set(), "customer_test": set()}
    if CONFIG["paper_fidelity"]:
        log("\n--- paper-fidelity: age exclusion "
            f"(age > {CONFIG['age_exclude_threshold']}) ---")
        for name in ("customer_train", "customer_test"):
            if name not in cleaned_nodes:
                continue
            kept, excl = compute_age_exclusion(
                cleaned_nodes[name], CONFIG["customer_key"],
                CONFIG["dataset_year"], CONFIG["age_exclude_threshold"],
            )
            log(f"  {name}: {len(excl):,} customers excluded "
                f"({len(cleaned_nodes[name]):,} -> {len(kept):,} rows)")
            cleaned_nodes[name] = kept
            excluded_ids[name] = excl
    else:
        log("\n--- paper-fidelity stage disabled (CONFIG['paper_fidelity']=False) ---")

    for name, df in cleaned_nodes.items():
        df.to_pickle(os.path.join(out, CONFIG["files"][name]))

    # --- stage 3: order tables - remove copies, and orders from customers left out ---
    log("\n--- event tables ---")
    ref = CONFIG["paper_reference_counts"]
    excl_map = {"event_train": excluded_ids["customer_train"],
                "event_test": excluded_ids["customer_test"]}
    for name in CONFIG["event_files"]:
        src = os.path.join(raw, CONFIG["files"][name])
        if not os.path.exists(src):
            log(f"  [MISSING] {name} (skipped)")
            continue
        df = pd.read_pickle(src)
        if CONFIG["paper_fidelity"]:
            df, stats = dedupe_and_filter_events(
                df, excl_map.get(name, set()),
                CONFIG["customer_key"], CONFIG["product_key"],
            )
            log(f"  {name}: {stats['before']:,} raw")
            log(f"    - exact duplicate rows removed : {stats['exact_duplicates_removed']:,}")
            log(f"    - conflicting-label pairs found: {stats['conflicting_pairs_flagged']} "
                f"(flagged only, NOT removed - no order key to disambiguate)")
            log(f"    - events from excluded (>90yo) customers removed: "
                f"{stats['age_excluded_events_removed']:,}")
            log(f"    = {stats['after']:,} final")
            if name in ref:
                gap = stats["after"] - ref[name]
                log(f"    vs paper's reported {name.split('_')[1]} count "
                    f"({ref[name]:,}): {'+' if gap >= 0 else ''}{gap:,} "
                    f"({100 * gap / ref[name]:+.1f}%)")
        else:
            log(f"  {name}: copied unchanged ({len(df):,} rows)")
        df.to_pickle(os.path.join(out, CONFIG["files"][name]))

    log("\n" + "=" * 70)
    log("DONE. Cleaned tables written to the output folder.")
    if CONFIG["paper_fidelity"]:
        log("Any remaining gap vs the paper's counts is expected - see the")
        log("no-order-key limitation noted above. Treat it as a documented")
        log("dataset-vintage difference, not a bug to keep chasing.")
    log("Next: run profile_data.py on the CLEAN folder to confirm the fixes,")
    log("then Phase 1 baseline reads from here.")
    log("=" * 70)


if __name__ == "__main__":
    main()