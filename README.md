# Returns Risk Engine

This project predicts which online orders are likely to be **sent back by the
customer** — before the order is even shipped — and shows those predictions on
a dashboard, so a team can decide what to do about the risky ones.

It has two parts:

1. **A machine-learning model.** It learns from past orders by looking at the
   connections between customers and the products they bought. It reproduces a
   2026 research paper, *"Returnformer"* by Cao, Zhang & Li
   ([Entropy 2026, 28, 72](https://doi.org/10.3390/e28010072)), using real
   fashion-retail data from ASOS UK.
2. **A web dashboard.** It lists orders from riskiest to safest, explains why
   each one was flagged, and lets staff record what they did about it.

> [!WARNING]
> **This is a demo. Never put real data in it.**
>
> - **It uses old orders, not live ones.** Every order on the dashboard is from
>   2021, and whether it was returned is already known. Nothing is predicting the
>   future.
> - **Order numbers, dates and company names are made up.** The original data
>   didn't include them, so they were invented. Order numbers always start with
>   `DEMO-ORD-`.
> - **The admin password is public.** It's written in this code and shown on the
>   login page.
> - **The security key has a public default.** If you run this anywhere without
>   setting `RETURNS_DASHBOARD_JWT_SECRET`, anyone can log in as an admin —
>   changing the password won't stop them.
>
> Before running it anywhere other than your own computer: set
> `RETURNS_DASHBOARD_JWT_SECRET`, set `RETURNS_DASHBOARD_COOKIE_SECURE=1` (only
> works over HTTPS), and remove the demo admin account. See `.env.example`.

## How well does it work?

Results are measured with a score called **AUC**. 0.5 means no better than
guessing; 1.0 means perfect.

| Which orders | This model | Simpler models | Better by |
|---|---|---|---|
| All orders | **0.876** | 0.833 | +0.043 |
| **Customers it has never seen before** | **0.767** | about 0.65 | **+0.117** |
| Customers it has seen before | 0.880 | about 0.838 | +0.042 |
| Products it has never seen before | 0.861 | about 0.800 | +0.061 |

**The second row matters most.** In the test data, 98.8% of customers had never
appeared in the training data — so a new customer is the normal case, not the
exception.

The "simpler models" are four standard tools (CatBoost, XGBoost, LightGBM and a
basic neural network) that look at each order on its own, ignoring the links
between customers and products. All four scored within 0.004 of each other —
0.8332, 0.8329, 0.8324 and 0.8293 — which shows the input data was prepared
consistently.

### The paper's extra parts didn't help

The paper builds a more complex model on top of a basic one called
**GraphSAGE**. Each extra part was built and tested here. None of them beat the
basic model, and some made it worse at handling new customers:

| Model | All orders | New customers |
|---|---|---|
| **GraphSAGE (basic)** | **0.876** | **0.767** |
| + Graph Transformer | 0.874 | 0.761 |
| + Node2Vec | 0.859 | 0.701 |
| + Node2Vec + attention fusion | 0.864 | 0.689 |

**Why:** the paper used a large, densely connected dataset. This project used a
much smaller sample — 35,348 customers and 400 products, with most customers
buying only one or two of them. The extra parts work by spotting patterns
across many connections, and this data doesn't have many. The basic model only
looks at each customer's and product's direct links, so it doesn't need them.

The full write-up is in
[`docs/checkpoint_phase0_phase3.md`](docs/checkpoint_phase0_phase3.md). The
code for those extra experiments isn't in this repository, so the results are
documented here but those particular runs can't be repeated from it.

## Getting started

You **don't** need the dataset to install the project or run its tests.

You need **Python 3.12** and **Node.js**.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

Type `python3.12`, not just `python3`. Many computers now have a newer Python
under the name `python3`, and this project's packages were tested on 3.12 — on
a newer version the machine-learning packages may not install.

### Run the tests

```bash
.venv/bin/python -m pytest backend/tests -q    # 87 tests
cd frontend && npm run build && cd ..          # checks and builds the website
cd frontend && npm run lint && cd ..           # checks the code style
```

You should see **87 tests pass**, the build succeed, and the style check report
**0 errors and 2 warnings**. The 2 warnings are known and harmless.

To run all **103** tests, install the machine-learning packages too:

```bash
.venv/bin/python -m pip install -r requirements-ml.txt
.venv/bin/python -m pytest backend/tests serving/tests -q    # 103 tests
```

## Running the dashboard

This part needs the data.

### 1. Get the data

The data isn't in this repository. It's about 708 MB of anonymised ASOS UK
orders from September–November 2021. **Ask the repository owner for access.**

The dataset's original licence terms aren't recorded anywhere in this project.
Check them before using the data for anything other than running this code, and
don't pass it on to others.

### 2. Put the files in place

Make a folder called `data` in the main project folder, and put all six files
in it. Don't rename them — the code looks for these exact names:

```
data/
├── event_table_training.p        31 MB
├── event_table_testing.p         33 MB
├── customer_nodes_training.p    179 MB
├── customer_nodes_testing.p     191 MB
├── product_nodes_training.p     137 MB
└── product_nodes_testing.p      137 MB
```

Git ignores the `data` folder, so these files can never be uploaded by mistake.

### 3. Build the dashboard's data file

The dashboard reads one file: `serving/output/orders_seed.json`. Build it by
running these five steps in order, from the main project folder. Each step uses
what the one before it made. You'll need the machine-learning packages
installed (see above).

```bash
.venv/bin/python clean_data.py      data          data/clean      # 1. clean the raw data
.venv/bin/python build_features.py  data/clean    data/features   # 2. prepare the model's inputs
.venv/bin/python sample_subgraph.py data/features data/graph train_test 20000   # 3. take a sample
.venv/bin/python build_graph.py     data/graph    train_test      # 4. link customers to products
.venv/bin/python serving/export_seed.py                           # 5. train the model, score the orders
```

**Keep `20000` exactly as written.** It sets the size of the sample, and it's
the value that gives the numbers in this README. A bigger number gives a much
bigger sample and different results.

All five steps take about a minute on a laptop. Step 5 trains the model from
scratch every time you run it.

### 4. Start it

```bash
./run_dev.sh
```

Then open **http://localhost:5173** in your browser. Use `localhost` — the
address `127.0.0.1` won't load here.

`run_dev.sh` sets up the database the first time you run it. Other options:

```bash
./run_dev.sh --reset-db                        # start again with a fresh database
                                               # (this deletes every user account)
./run_dev.sh --help
.venv/bin/python -m backend.scripts.seed_db    # set up the database yourself
```

If the data file from step 3 is missing, `run_dev.sh` stops and tells you how to
make it. You can still start the server on its own to look around:

```bash
.venv/bin/uvicorn backend.app.main:app --port 8000
```

It runs with no data — you can log in, but there won't be any orders.

### Optional extras

Not needed for the dashboard:

```bash
.venv/bin/python profile_data.py    data/clean       # a report describing the raw data
.venv/bin/python train_baselines.py data/features    # train the four simpler models
.venv/bin/python train_gnn.py       data/graph train_test data/features/baseline_results.csv
```

The last one prints the results shown at the top of this page.

### About the data

The data is anonymised: customer and product IDs are scrambled, and details
like country and brand are replaced with codes such as `Country_A` and
`Brand_A`. There are no names. It also has 13 return-reason codes labelled with
letters — nobody knows what they actually mean, so this project doesn't guess.

## What's in the repository

```
├── clean_data.py, build_features.py, sample_subgraph.py,
│   build_graph.py, train_gnn.py, …     the machine-learning steps
├── serving/       turns the model's scores into the dashboard's data file
├── backend/       the server (Python, FastAPI, SQLite)
│   └── tests/     87 tests
├── frontend/      the website (React, TypeScript)
├── docs/
│   ├── checkpoint_phase0_phase3.md     the full machine-learning write-up
│   └── history/PROJECT_LOG.md          a diary of how the project was built
└── run_dev.sh     starts everything
```

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the code is organised, and why.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to work on it, and the mistakes to
  avoid.

## Known limits

- **It can only score the 16,246 orders in its sample.** There's no way yet to
  score a brand-new order. This is the biggest gap between this demo and a real
  product.
- The trained model isn't saved, so it's retrained every time.
- The website has no automated tests.
- Changing the database layout means starting with a fresh database — there's
  no upgrade system.
- Bulk actions can't be undone. The dashboard warns you before you run one.
- Alerts use a simple threshold, not a proper statistical test.

The full list of open issues is in section 9 of
[`docs/history/PROJECT_LOG.md`](docs/history/PROJECT_LOG.md).
