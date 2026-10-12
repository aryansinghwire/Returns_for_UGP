# Codebase Guide

> A practical guide to the project structure, data flow, alert logic, and key design decisions.
>
> **Project history:** [`docs/history/PROJECT_LOG.md`](docs/history/PROJECT_LOG.md)

## Contents

1. [Project at a glance](#project-at-a-glance)
2. [Where to make changes](#where-to-make-changes)
3. [How predictions reach the dashboard](#how-predictions-reach-the-dashboard)
4. [How alerts work](#how-alerts-work)
5. [Key design decisions](#key-design-decisions)
   - [Model and data sampling](#model-and-data-sampling)
   - [Invented data and explanations](#invented-data-and-explanations)
   - [Backend and security](#backend-and-security)
   - [Website behaviour](#website-behaviour)
   - [Local development](#local-development)

---

## Project at a glance

The project uses a **Graph Neural Network (GNN)** to score orders, then presents those scores in a web dashboard.

| Part | What it does | Main technology or location |
|---|---|---|
| Data preparation | Cleans raw data and creates model features | Python scripts in the data pipeline |
| Graph and model | Connects customers with products and trains the model | `build_graph.py`, `train_gnn.py` |
| Prediction output | Scores the test orders and adds demo details and explanations | `serving/export_seed.py` |
| Data storage | Keeps original scores, current order status, and action history separate | SQLite |
| Backend | Applies permissions and provides data to the website | FastAPI |
| Dashboard | Shows orders, risk levels, filters, and actions | React |
| Alerts | Flags groups whose recent return rate is higher than normal | `backend/app/services/alerts.py` |

> **Important:** This is a prototype. Order numbers, dates, and company names shown in the dashboard are invented. The model scores the sample's test orders; it does not yet score new orders.

## Where to make changes

Use this table as the starting point when updating the project. Check the files in the final column too, where listed.

### Model and data

| If you want to change… | Start here | Also check |
|---|---|---|
| How the model works | `train_gnn.py` — `GNNEncoder`, `EdgeDecoder`, `Model` | `serving/export_seed.py` uses the same classes |
| A model setting, such as training rounds | `train_gnn.CONFIG` | `serving/export_seed.py` reads settings from here |
| The size of the sample | `sample_subgraph.py` — `n_seed_products` and the command-line value | `export_seed.py` warns if the test-order count is not `16,246` |
| Which information the model learns from | `build_features.py` | `build_graph.py`, `export_seed.py`, `serving/reasons.py`, then the backend |
| Explanations shown for each order | `serving/reasons.py` | Thresholds in `serving/config.py`; run `export_seed.py --reasons-only` to refresh explanations without retraining |
| Invented order numbers, dates, and company names | `serving/config.py` | Keep all invented details defined here |

### Backend and security

| If you want to change… | Start here | Also check |
|---|---|---|
| Database tables | `backend/app/models.py` | Missing tables are created automatically, but missing columns are not added |
| A server URL or endpoint | `backend/app/routers/` | Keep route handlers short; put the main logic in `services/` |
| What a user can see or do | `backend/app/deps.py` | `config.ROLE_LEVELS` and `constants.ROLES` |
| Actions available to staff | `backend/app/constants.py` | Update `frontend/src/api/types.ts` as well; both files must match |
| When alerts appear | `backend/app/config.py` | All four alert settings are in this file |
| Order status or action history | Relevant backend services and models | Keep original model scores separate from later changes |

### Dashboard

| If you want to change… | Start here | Also check |
|---|---|---|
| Low, medium, and high risk limits | `frontend/src/lib/risk.ts` | `backend/app/services/dashboard.py` must use matching limits |
| The order list or its filters | `frontend/src/pages/QueuePage.tsx`, `components/FilterPanel.tsx` | `routers/orders.py` shares a filter between the list and the chart above it |
| Colours, fonts, or spacing | `frontend/src/index.css`, `lib/controls.ts` | Only `lib/risk.ts` should use colour to communicate meaning |

---

## How predictions reach the dashboard

The pipeline turns raw data into model scores, loads the results into SQLite, and serves them to the React website.

### Pipeline overview

| Step | Script or location | What happens |
|---|---|---|
| 1. Clean the data | `clean_data.py` → `data/clean/` | Fixes known problems in the six raw ASOS UK data files. The raw files are not included in this repository. |
| 2. Build features | `build_features.py` → `data/features/` | Converts each order into numerical features the model can use. |
| 3. Select a connected sample | `sample_subgraph.py` | Selects **400 products, 35,348 customers, and 36,114 orders**. The sample contains **19,868 training orders (Sep–Oct)** and **16,246 test orders (Oct–Nov)**. |
| 4. Build the graph | `build_graph.py` → `data/graph/` | Connects each customer to the products they bought. |
| 5. Train and score | `train_gnn.py`, `serving/export_seed.py` | Trains on training orders only, then trains the same model again in `export_seed.py` and scores the 16,246 test orders. Using test orders during training would cause data leakage. |
| 6. Add demo details | `synth.py`, `reasons.py` | `synth.py` adds invented order numbers, dates, and company names. `reasons.py` adds a short explanation for each score. |
| 7. Write prediction output | `serving/output/orders_seed.json` | Stores the results in a JSON file of about **29 MB**. This file is not included in the repository. `export_seed.py` matches scores to orders by list position, so it first checks that both lists have the same length. |
| 8. Load the database | `backend/scripts/seed_db.py` | Loads the JSON results into SQLite. |
| 9. Display the results | FastAPI → React website | The backend reads the database and provides the information shown in the dashboard. |

### What the database stores

| Table | Purpose | Can it change? |
|---|---|---|
| `orders` | Stores the original information the model saw and scored | No — the original records and scores remain unchanged |
| `order_status` | Stores the current status and any updated score value | Yes — it reflects later changes |
| `intervention_log` | Records what people did and when | New entries are added; old entries are not changed or removed |
| `tenants`, `users`, `automated_rules`, `baseline_stats` | Store company, account, rule, and baseline information | Depends on the type of record and how the system uses it |

> **Score history:** The model's original score is never overwritten. If someone changes a score, the updated value goes into `order_status`, and the change is recorded in `intervention_log`. This keeps the original prediction available for review.

---

## How alerts work

Alerts are **separate from the GNN model**. They identify groups of orders whose recent return rate is higher than the group's usual rate.

### 1. Establish the normal rate

When the database is loaded, `seed_db.py` calculates the usual return rate for each group and stores it in `baseline_stats`. A group can be all orders for one **product**, one **country**, or one **product type**.

### 2. Compare recent and normal rates

`backend/app/services/alerts.py` calculates:

| Measure | Meaning |
|---|---|
| **Recent rate** | Share of recent orders in the group that were returned |
| **Normal rate** | The group's usual return rate, stored in `baseline_stats` |
| **Gap** | `recent rate − normal rate` |

### 3. Apply the alert thresholds

| Condition | Result |
|---|---|
| Gap is **at least `0.15`** and the group has **at least 15 recent orders** | Raise an alert |
| Gap is **at least `0.25`** | Mark the alert as **high** |
| Gap is at least `0.15` but below `0.25` | Mark the alert as **medium** |

The minimum of 15 orders helps prevent random changes in small groups from triggering too many alerts. The test data has only about 397 different products.

### Alert settings

All four settings are in `backend/app/config.py`:

| Setting | Controls |
|---|---|
| `ALERT_MIN_GAP` | Minimum gap needed to raise an alert (`0.15`) |
| `ALERT_MIN_N` | Minimum number of recent orders (`15`) |
| `ALERT_HIGH_GAP` | Gap at which an alert becomes high (`0.25`) |
| `ALERT_WINDOW_DAYS` | Number of days covered (`14`) |

Alerts are **not saved** in the database. They are recalculated whenever someone opens the page.

> **Date rule:** The 14-day window is counted back from the **newest order in the dataset**, not from today. The dates are invented and end in 2021, so using today's date would not find the intended orders. `services/dates.py` keeps this rule consistent between alerts and the order-list date filter.

The alert logic is the only part of the project that reads the real return outcomes. It uses group totals only, never the outcome of an individual order.

---

## Key design decisions

This section explains the main choices in the project and why they were made.

### Model and data sampling

**Use the simplest model that performs best.** The basic GraphSAGE model performed better than the more complex versions, so it is the model used in the project. The other versions were still built and tested to confirm that they did not improve the results.

**Use a small, connected sample.** The full dataset contains many separate groups of customers and products that are not linked to each other. A connected sample is needed to test a model that learns from customer-product links. The write-up's limitations section explains the trade-off.

**Show the test orders in the dashboard.** The model can score only the 16,246 test orders in the sample. Those are the orders shown on the dashboard; new orders cannot be scored yet.

### Invented data and explanations

**Label invented details clearly.** The original data does not contain order numbers, dates, or company names, so the project creates them for the dashboard. To make their status clear:

- Invented order numbers start with `DEMO-ORD-`.
- Every server response includes `X-Prototype: true`.
- Every page displays a prototype banner.
- The banner wording is stored in `serving/config.PROTOTYPE_NOTICE` so it stays consistent.

**Do not reveal actual return results for individual orders.** The dataset records whether each order was returned. Showing that result beside an individual order would reveal the answer the model is meant to predict. Actual results are shown only as group totals in alerts and reports, labelled as past results.

**Keep explanations focused on meaningful details.** Explanations do not use the 13 letter-based return-reason codes because their meanings are unknown. They also do not mention age, year of birth, gender, or premium membership. Age, year of birth, and gender are protected characteristics; the effect of premium membership has not been measured. The model still uses all four fields, but staff-facing explanations do not.

### Backend and security

**Use a database instead of a plain file.** The system needs to save score changes and user actions reliably, and search through more than 16,000 orders quickly. A plain file would need to be rewritten in full whenever anything changed.

**Keep the three main tables separate.** One stores what the model saw, one stores each order's current status, and one records people's actions. Separating them preserves the history of changes.

**Know the limits of database setup.** There is no full database migration system. The server can create missing tables, but it cannot add missing columns to an existing table. On startup, it fixes one known older database layout by deleting and recreating the automatic-rules table. This is safe only because the rules can be entered again quickly.

> **Do not use that repair approach for the `users` table.** It holds the only copy of each user's account.

**Enforce company-level data separation in the server.** The website does not control access separation. Only the platform admin can view data across companies; other users can see only their own company's data. If a user requests another company's data, the server returns an error rather than silently showing different data.

**Check user roles against the database on every request.** The server does not rely on the role stored in a login token. Otherwise, a user whose access had been reduced or disabled could keep the old permissions until the token expired — up to eight hours later.

**Use score ranges for rules.** Rules are based on a range of scores, not just a minimum. This allows medium-risk orders to trigger lower-cost actions, such as emails, while high-risk orders can trigger more expensive actions, such as phone calls. The ranges can be configured so rules do not overlap.

**Run rules only when a user clicks the button.** Automatic scheduling is unnecessary for a demo.

### Website behaviour

**Confirm bulk actions before running them.** Applying rules can affect thousands of orders. Before running them, a confirmation box shows how many orders each rule will affect. The confirm button stays disabled until these numbers have loaded. The box also clearly states that the action cannot be undone.

**Keep the action history append-only.** An undo feature was built and worked, but it made the history table more complicated. Since the table is intended to keep adding records without changing or deleting older ones, a clear warning was simpler than an undo feature.

**Record delivery approval as an action.** Marking an order as `Approved for delivery` is a real decision, so the system records it.

**Use colour only to show risk.** The rest of the interface uses black, white, and grey. Green, yellow, and red indicate risk, using the same limits as the labels **low**, **medium**, and **high**. The score and written label always appear too, so colour is not the only way to understand the risk level.

**The reporting page is disabled, not deleted.** Its link has been removed, and its URL redirects elsewhere. The code remains in the project, but the page is no longer used. Whether to restore or remove it is undecided; see section 9 of the project log.

### Local development

**Use `run_dev.sh` to start the project reliably.** Starting everything by hand is easy to get wrong:

- The commands must use the correct Python version.
- The server must be started from the main project folder.
- The website must use `localhost`, not `127.0.0.1`.

An old server process could also stay running in the background while a new server failed to start. The website might then show old code without an obvious error. `run_dev.sh` stops old copies first and checks that the server has started successfully.

---

*For the build history and unresolved decisions, see [`docs/history/PROJECT_LOG.md`](docs/history/PROJECT_LOG.md).*
