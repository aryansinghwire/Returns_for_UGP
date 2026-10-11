# Project Log — Pre-Dispatch Returns Risk Engine

A working record of what has been built, why it was built that way, how to run it,
and what is still open. Reconstructed from the git history (`9ef3576`..`e4b3987`)
and the current code.

> **This is a diary of how the project was built, not a guide to using it.**
>
> It was written as the work happened, so it's long and technical. To
> understand the project, read these instead:
>
> - [`README.md`](../../README.md) — what it is and how to run it
> - [`ARCHITECTURE.md`](../../ARCHITECTURE.md) — how the code is organised
> - [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — how to work on it
>
> **About the short codes like `9ef3576`.** These are references to changes in
> the project's original, private history. They don't exist in this public
> copy, so you can't look them up here — read them as labels for "the change
> that did this". The same goes for some files and folders the entries
> mention, such as `docs/review/` and `archive/`: they're kept privately and
> aren't in this copy.
>
> **Old entries are not rewritten.** That's what keeps it a reliable record,
> so the entries below keep their original wording - apart from a few
> passages about the editor setup used during development, which were
> removed. New entries are added to the end.

**Last updated:** 2026-10-01 · **Branch:** `main` (fast-forwarded to
`feature/ops-dashboard-prototype`; the two branches are the same commit)

Companion documents: [`checkpoint_phase0_phase3.md`](../checkpoint_phase0_phase3.md)
is the deep technical record of the ML phases; `archive/README.md` explains
what is parked and why, in the private archive this log belongs to. This log is
the narrative that ties them together.
(`project_structure.md`, the file-tree map, was deleted in the 2026-10-01 docs
reorganization; it is recoverable from commit `afb806a` if it is ever wanted.)

---

## 1. What this project is

Two halves, built in order:

1. **An ML pipeline** reproducing Cao, Zhang & Li, *"Returnformer: A Graph
   Transformer-Based Model for Predicting Product Returns in E-Commerce"*
   (Entropy, 2026), against the internal PRD for a pre-dispatch returns risk
   engine. It predicts, before dispatch, whether an order will be returned —
   using a customer–product bipartite graph over real ASOS UK fast-fashion data.
   **Shipped model: GraphSAGE**, 0.876 overall AUC / 0.767 cold-customer AUC.

2. **An ops dashboard prototype** — the product half of the PRD §9 — sitting on
   top of that model: a risk-sorted review queue, order drill-down, manual
   override, logged interventions, spike alerts, per-tenant automated rules, and
   a role-gated multi-tenant admin surface.

The end goal is a multi-tenant product: tenants sign up, connect or upload
their own order history, and get the same queue over their own data. The current
build is that product running on one dataset, with tenant assignment simulated —
see §9 for what still stands between here and there.

---

## 2. Timeline

| Date | Commit | What landed |
|---|---|---|
| 2026-09-07 | `9ef3576` | Initial commit — ML pipeline, phases 0–3 complete |
| 2026-09-08 | `d3ee1b5` | **Layer 1** — score export (`serving/`) |
| 2026-09-08 | `80610bd` | **Layer 2** — FastAPI + SQLite backend |
| 2026-09-11 | `f6c29e2` | **Layer 3** — React frontend |
| 2026-09-12 | `a332781` | Archive work not part of the live system |
| 2026-09-12 | `afb806a` | Tenant Admin rename, per-tenant config, score windows |
| 2026-09-23 | `be8fc81` | Tenant isolation for every role, proceed-with-delivery, sweep warning |
| 2026-09-23 | `e4b3987` | `run_dev.sh` |

---

## 3. The ML pipeline (phases 0–3)

### Phase 0 — profiling and cleaning
`profile_data.py`, `clean_data.py`. Six pickle tables (event / customer-node /
product-node × train / test). Produced `data_profile_report.md`.

The finding that drove everything downstream: **cold-start is a customer problem,
not a product problem.** 78–99% of real test traffic is customers never seen in
training. The graph is extraordinarily sparse (~1.1 edges per node).

Hard data constraints discovered here, which constrain every later layer:
- No real order ID, no per-order timestamp, no customer/product/brand names.
  Only hashed IDs and anonymized one-hot buckets (`Country_A..I`, `Brand_A..K`,
  `productType_A..K`).
- The 13 lettered return-reason buckets have **no known real-world meaning**.
  Nothing in this project may assign them one.

### Phase 1 — features, eval harness, tabular baselines
`build_features.py`, `eval_harness.py`, `train_baselines.py`.

Four tuned baselines landed within 0.004 AUC of each other — agreement that
validates the feature pipeline rather than any one algorithm:

| Model | AUC | Warm AUC | Cold AUC |
|---|---|---|---|
| CatBoost | **0.8332** | 0.8391 | 0.6499 |
| XGBoost | 0.8329 | 0.8388 | 0.6477 |
| LightGBM | 0.8324 | 0.8382 | 0.6504 |
| MLP | 0.8293 | 0.8350 | 0.6391 |

A leakage probe settled the obvious objection: `customerReturnRate` alone scores
0.801 AUC, full models reach 0.833 — a real margin, so the models combine signal
rather than echoing one column.

**Baseline floor: ~0.833 AUC, ~0.65 on cold customers.** This is the number the
graph work had to clear.

### Phase 2 — bipartite graph + GraphSAGE
`sample_subgraph.py`, `build_graph.py`, `train_gnn.py`.

Subgraph: 400 products, 35,348 customers, 36,114 edges (19,868 train Sep–Oct /
16,246 test Oct–Nov), **98.8% of test customers absent from the training graph**.

| Slice | GraphSAGE | Baseline | Δ |
|---|---|---|---|
| Overall | **0.876** | 0.833 | +0.043 |
| Cold customer | **0.767** | ~0.65 | **+0.117** |
| Warm customer | 0.880 | ~0.838 | +0.042 |

The central hypothesis holds: graph structure lifts exactly the population the
tabular models were weakest on.

### Phase 3 — the full Returnformer stack, built as an ablation
`archive/ablations/`: Graph Transformer, Node2Vec, attention fusion.

| Model | Overall AUC | Cold-customer AUC |
|---|---|---|
| **GraphSAGE** | **0.876** | **0.767** |
| + Graph Transformer | 0.874 | 0.761 |
| + Node2Vec (concat) | 0.859 | 0.701 |
| + Node2Vec + fusion | 0.864 | 0.689 |

**Every component the paper adds on top of a basic GNN failed to improve on plain
GraphSAGE, and the topological additions actively degraded the cold-customer case.**
This contrasts with the paper, and the contrast has a concrete explanation: the
paper runs on a dense full-scale graph where topological position encodes
non-obvious patterns; this project runs on a sparse subgraph where it does not.
Message-passing over direct neighbours needs no connectivity; global topological
methods do, and this data starves them.

Phase 4 (GEA, KAN) was deliberately not pursued — see `checkpoint_phase0_phase3.md` §10.

---

## 4. The dashboard

### Layer 1 — `serving/` (score export)

`export_seed.py` retrains GraphSAGE on the sampled subgraph (importing
`Model`/`GNNEncoder`/`EdgeDecoder` from `train_gnn.py` rather than duplicating
them), scores the held-out test edges, and joins the scores back onto the raw
test-edge feature rows to write `serving/output/orders_seed.json`.

The join is **positional**, and it is safe for a verified reason: `build_graph.py`
does `pd.concat([tr, te])` and never reorders, so `test_prob` is in exactly the
row order of `sub_train_test_test.p`. `export_seed.py` asserts
`len(display_df) == len(test_prob) == 16246` as a permanent regression check on
that assumption.

- `config.py` — the single place defining what is real vs. synthesized.
- `synth.py` — order ids (`DEMO-ORD-######`), dates (seeded uniform over
  Oct–Nov 2021), tenant assignment (per **customer**, weighted 40/35/25, so one
  customer's orders stay in one tenant).
- `reasons.py` — rule-based contributing reasons off real named columns only.

### Layer 2 — `backend/` (FastAPI + SQLAlchemy 2 + SQLite)

| Method & path | Gate | Purpose |
|---|---|---|
| `GET /api/health` | none | liveness |
| `GET /api/meta` | any | seed provenance + prototype notice |
| `GET /api/tenants` | any | list tenants |
| `POST /api/tenants` | `admin` | onboard a tenant |
| `GET /api/orders` | any | queue list (filter / sort / paginate) |
| `GET /api/orders/{id}` | any | detail — **never** returns ground truth |
| `POST /api/orders/{id}/override` | `ops_analyst`+ | manual score override |
| `POST /api/orders/{id}/actions` | `ops_analyst`+ | log an intervention |
| `PATCH /api/orders/{id}/actions/{log_id}` | `ops_analyst`+ | record an outcome |
| `GET /api/orders/{id}/history` | any | full log for one order |
| `GET /api/dashboard` | any | landing tiles: orders by period, actions all-time |
| `GET /api/reporting/baseline-vs-actual` | any | cohort comparison *(route disabled in UI)* |
| `GET /api/alerts` | any | live spike list |
| `GET /api/rules` | any | per-tenant rules |
| `POST /api/rules` · `PATCH /api/rules/{id}` | `tenant_admin`+ | rule CRUD |
| `POST /api/rules/evaluate` | `tenant_admin`+ | manual sweep |
| `GET /api/audit-log` | `tenant_admin`+ | oversight view |

**Tables:** `tenants`, `orders` (immutable), `order_status` (1:1 mutable),
`intervention_log` (append-only), `automated_rules`, `baseline_stats`.
A fresh seed yields 16,246 orders, 3 tenants, 1,239 baseline stats.

**Spike alerts are not persisted** — computed live: flag a cohort when
`actual − baseline ≥ 0.15` **and** `n ≥ 15` over a trailing 14-day window. The
minimum-sample guard matters because only ~397 distinct products exist in the
test set, so small cohorts would otherwise fire constant noise.

### Layer 3 — `frontend/` (React 19 + Vite + TS + Tailwind 4 + TanStack Query + Recharts)

Pages: **Dashboard** (`/dashboard`, the post-sign-in landing for every role),
**Queue** (`/queue`), **Order Detail** (`/orders/:orderId`), **Alerts**
(`/alerts`), **Escalations** (`/escalations`, `tenant_admin`+), **Admin**
(`/admin`). **Reporting** (`/reporting`) redirects to the queue — the route is
disabled, the page component and its endpoints retained.

Notable components: `ScoreRangeSlider` (dual-thumb window), `SweepConfirm`
(the warning gate in front of a bulk sweep), `NavSidebar`, `HistoryTimeline`,
`PrototypeBanner`, `RiskDistribution`, `RiskMixBar`, `StatTile`.

---

## 5. Key files and modules

```
serving/export_seed.py          trains + scores + writes the seed JSON
serving/config.py               the real-vs-synthesized boundary
backend/app/deps.py             role gating and tenant scoping — the security core
backend/app/models.py           the six tables
backend/app/main.py             app assembly, prototype marker, schema self-heal
backend/app/services/           queue, reporting, alerts, rules_engine
backend/scripts/seed_db.py      loads seed JSON, computes baseline_stats
backend/tests/test_api.py       14 tests against a temp DB
frontend/src/api/{client,hooks,types}.ts   fetch layer, query hooks, shared types
frontend/src/context/AppContext.tsx        role / tenant / actor state
frontend/src/components/SweepConfirm.tsx   the no-undo confirmation gate
run_dev.sh                      one-command launcher for both servers
```

---

## 6. Design decisions and why

### ML

**Ship the simplest graph model.** GraphSAGE beat every more complex variant.
Building the full Returnformer stack anyway — as an ablation rather than as the
deliverable — turned "we didn't finish the paper" into a measured finding with a
structural explanation. This is a more informative result than a rote reproduction.

**Sample a small connected subgraph rather than partition the full graph.** The
full graph is disconnected at this scale; a connected subgraph is the only setting
where message-passing is actually being tested. The cost is stated honestly in the
checkpoint's limitations section.

**Replay held-out test edges as the live queue.** The model can only score the
16,246 test edges of the sampled subgraph. Those are therefore exactly "the orders
the dashboard can interact with." There is no path today to score an arbitrary
new order.

### Honesty about synthetic data

The dataset has no order id, no per-order date, and no tenant structure. All three
had to be synthesized or there would be no queue, no timeline, and no multi-tenant
view at all — so each is made unmistakably artificial and labelled at every layer:

- Order ids are always `DEMO-ORD-######`.
- `serving/config.PROTOTYPE_NOTICE` is the single source of the disclaimer; it
  flows through `/api/meta` into a persistent `<PrototypeBanner/>` on every page,
  rather than being hardcoded per component.
- Tenant names are obviously fictional and **never** conflated with
  `product_brand_bucket`, which is a real (anonymized) product attribute.
- Every HTTP response carries `X-Prototype: true`.
- Reasons text cites only real, named variables and thresholds — **never** the 13
  lettered return-reason buckets, which have no decodable meaning.
- `is_returned_ground_truth` is never exposed on an individual order. It appears
  only pre-aggregated in reporting and alerts, labelled as an observed outcome
  rate from a backtest replay.

### Backend

**SQLite over a flat file.** Overrides and intervention logs need real
transactional read-modify-write and indexed filter/sort over 16k rows. A JSON file
would mean rewriting the whole array on every write.

**Three tables with three different mutability rules**, because they answer three
different questions: `orders` is immutable (what the model saw), `order_status` is
mutable 1:1 state (where the order stands now), `intervention_log` is append-only
(what people did, and when). Collapsing them would destroy the audit trail.

**No migrations, so the schema self-heals.** `Base.metadata.create_all()` only.
When `automated_rules` moved from a single `score_threshold` to a
`score_min`/`score_max` window, an existing database would have kept the old column
and failed every rule query. `main._drop_stale_rules_table()` drops *just that one
table* on startup when it detects the old column — safe because rules are
configuration a user types in, not seeded data, so orders, overrides and the audit
log are untouched and only stored rules are lost, once.

**Role simulation via `X-Role` / `X-Actor-Tenant` headers is explicitly not a
security boundary.** Anyone can send any header. It exists so the role model can be
*demonstrated*; a real deployment reads both off the session. This is stated rather
than disguised.
> **Superseded 2026-10-01.** Both headers are gone. Identity is now a signed JWT
> in an HttpOnly cookie resolved against a `users` row — the "real deployment"
> this paragraph anticipated. Kept because it records why the simulation was
> acceptable while it lasted. See §10, 2026-10-01.

**Tenant isolation is a property of the API, not of the UI.** One dependency,
`deps.get_scoped_tenant_or_none`, pins every non-`admin` caller to its own tenant,
and every tenant-bearing endpoint goes through it. A `?tenant=` pointing elsewhere
is **refused with 403, not quietly ignored** — silently narrowing would teach a
caller that their request succeeded. Only `admin` (Platform Admin / support) is
cross-tenant. A blank `X-Actor-Tenant` counts as absent, so a scoped request without
a tenant gets a 403 explaining the problem rather than a 404 for a tenant named `""`.

**`update_rule` checks scope against the rule's owner, not a query parameter** —
the rule id already determines the tenant, so trusting the parameter would be a
hole.

**Rules fire on a score *window*, not a floor.** `score_min`/`score_max` let a
tenant route a mid band to a cheap action and a top band to an expensive one
without the two overlapping, which a single threshold cannot express.

**The sweep is manual-trigger, not scheduled.** APScheduler or Celery would be
over-engineering here. Documented as a scope simplification in
`services/rules_engine.py`, not left as an implied oversight.

### Frontend

**A bulk sweep asks first, and shows its work.** The sweep can action thousands of
orders in one click. `SweepConfirm` opens a warning stating what will actually
happen, with a live per-rule count taken from the existing queue filters (no new
endpoint), and confirm stays disabled until those counts resolve — so the number is
always seen before it is accepted. It says plainly that orders leave the review
queue, who the actions will be attributed to, and that **there is no undo**.

**A sweep-revert feature was built and then deliberately discarded.** It worked —
sweep ids, a two-pass restore, per-order counting — but it added a mutable
dimension to an append-only log and a lot of surface area for a prototype. It was
reverted in favour of the warning above: making the irreversible action *clear* is
cheaper than making it reversible, and it was the right call for this scope.

**`proceed_with_delivery` is a first-class action.** "Reviewed and cleared" is a
real decision worth recording, not the absence of one. It is usable both manually
and as a rule's action.

**One shared `ACTION_LABELS`.** Two components previously each kept a private copy
of the action-label map, so a new action could appear in one place and not the other.

**The tenant picker is for the Platform Admin only.** Ops Analyst and Tenant Admin
each belong to exactly one tenant, chosen once in the role panel; a second control
in the sidebar would just be a second way to say the same thing. The Platform Admin
keeps it because choosing a tenant to inspect is their actual job.

**Stale roles are migrated on read.** When `ops_manager` became `tenant_admin`, any
browser holding the old value in `localStorage` would have 403'd every request;
`AppContext.readStoredRole()` retires it.

**Scoped queries wait until the tenant is known**, so a first visit does not fire a
request that is certain to be refused.

**Reporting is disabled, not deleted** — nav link removed, route redirected, page
component and endpoints left intact so it can be switched back on by restoring one
route and one link.

### Repo hygiene

**Archive, never delete.** `archive/` holds the Phase 3 ablations, superseded
checkpoints, parked exploratory work, and a one-off diagnostic — each with an entry in
`archive/README.md` saying what it is, why it is parked, and how to restore it.
`data/graph/` now holds only the three files `export_seed.py` actually reads.

**`run_dev.sh` exists because three things were easy to get wrong**: the
`.venv/bin/` prefix (uvicorn is not on PATH), running the backend from the repo
root (it is imported as the dotted path `backend.app.main`), and using `localhost`
rather than `127.0.0.1` for Vite, which binds IPv6 only here. Worse, **a stale
uvicorn keeps port 8000 while the new one silently fails to bind** — the page loads
and serves old code with no error anywhere. The script clears leftovers before
binding, polls `/api/health` (macOS has no `timeout`), and prints the tail of the
log if either server fails. Vite is `exec`'d directly rather than run through
`npm run dev`, because npm puts two processes between the script and the server, so
the tracked pid was not the one holding the port and Ctrl-C orphaned Vite.

---

## 7. How to run

```bash
./run_dev.sh              # start both servers, stream logs, Ctrl-C stops both
./run_dev.sh --reset-db   # wipe and reseed the database first
./run_dev.sh --help
```

Then open **http://localhost:5173** — `localhost`, not `127.0.0.1`.

The script runs `npm install` and seeds the database if either is missing. It will
not generate the seed JSON for you; if `serving/output/orders_seed.json` is absent
it tells you to run the export, which retrains GraphSAGE and takes a while.

By hand, if you prefer:

```bash
# once: regenerate the scored seed data (slow — retrains the model)
.venv/bin/python serving/export_seed.py

# once: load it into SQLite (--force wipes and reseeds)
.venv/bin/python -m backend.scripts.seed_db

# terminal 1
.venv/bin/uvicorn backend.app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

`backend/orders.db`, `serving/output/`, `data/` and `.run-logs/` are all gitignored.

---

## 8. How to test

```bash
.venv/bin/python -m pytest backend/tests serving/tests -q   # 92 tests, ~1.5s
cd frontend && npm run build                                # tsc -b && vite build
cd frontend && npm run lint                                 # oxlint
```

The backend suite covers the queue list, that detail omits ground truth, override
writing both tables, role gating (403 then 201), cross-tenant rule writes being
refused, rules listing scoped to the caller's tenant, window ordering validation,
the sweep respecting the window, `proceed_with_delivery` being accepted, an Ops
Analyst being pinned to its own tenant, a scoped role with no tenant being refused,
and an unknown role 403.

**There are no frontend tests.** UI verification has been done by hand and with
throwaway headless-Chromium (Playwright) scripts run from a scratchpad — deliberately
never added as a project dependency. That is a gap, not a decision; see below.

---

## 9. Open issues

**Version control**

- ~~**`data/clean_data.py` is not in git.** It is a Phase 0 pipeline source file, but
  it lives inside `data/`, which `.gitignore` excludes wholesale for being ~1.5 GB.
  `git check-ignore` confirms it. It exists only on this machine. It should be moved
  out of `data/` (or negatively excepted) before anything else — it is the one piece
  of pipeline source that a disk failure would take with it.~~
  **Resolved 2026-10-09** — moved to the repo root as `clean_data.py`, beside the
  seven pipeline scripts that were already there. `.gitignore` is unchanged; `data/`
  stays excluded wholesale. See §10, 2026-10-09.

**Not production-ready by design**

- ~~**No authentication.** `X-Role` and `X-Actor-Tenant` are a simulation. The tenant
  *scoping* logic is real and tested, but the identity it scopes on is self-asserted.~~
  **Resolved 2026-10-01** — email/password accounts, bcrypt hashes, and a JWT session
  cookie. The scoping logic is unchanged; it now scopes on a verified identity. What
  remains is narrower and listed below.
- **Signup lets a user pick their own role.** Anyone may take `tenant_admin` on any
  listed tenant, which carries that tenant's rule editing and audit log. A deliberate
  prototype affordance, labelled on the signup page and in `/api/auth/signup`'s
  description — not an oversight.
- **The demo platform admin's password ships in the repo and is printed on the login
  page.** Intentional, for a prototype whose point is being openable from a URL. It
  also means this build must never hold real data.
- **The JWT signing key has a fixed development default.** Anyone with the repo can
  forge an admin session against a server that has not set
  `RETURNS_DASHBOARD_JWT_SECRET`.
- **No refresh token, rate limiting, lockout, password reset or email verification.**
  A session lasts 8 hours and then the next request 401s into the login page.
- **No migrations.** The schema self-heals for exactly one known change; any further
  model change needs a fresh seed or another hand-written repair. `create_all` adds
  missing *tables* (which is how `users` appeared on existing databases for free) but
  never missing *columns*. A later change to `users` must not copy the
  `_drop_stale_rules_table` pattern: that one is safe only because rules are cheap,
  re-typeable config, whereas `users` holds the only copy of every account.
- **The sweep has no undo.** Deliberate, and warned about — but still true.
- **Alerts are a threshold check, not a hypothesis test.** Fine for a prototype,
  not a statistical claim.

**ML / data**

- **The trained model is never persisted.** `train_gnn.py` trains in memory and
  saves nothing, so `export_seed.py` retrains from scratch on every run. Fine at
  this scale, blocking for anything resembling serving.
- **Only the 16,246 sampled test edges can be scored.** There is no path to score
  an arbitrary new order — the single largest gap between this prototype and a
  usable system.
- **The queue is a backtest replay**, not live traffic with unknown outcomes. The
  banner says so; any write-up must too.
- **Tenant assignment is simulated.** Orders are dealt to three fictional tenants
  per customer; real tenancy comes from whose account uploaded the data. Nothing
  downstream depends on the simulation, but every tenant figure in the UI is an
  artefact of it.

**Loose ends**

- **The Queue's Tenant column is now redundant** for Ops Analyst and Tenant Admin,
  who can only ever see one tenant. Still needed for the Platform Admin. Unresolved.
- **Reporting is disabled but its code is retained** — dead code by intent, which
  will rot if left indefinitely. Either re-enable it or archive it.
- **No frontend test suite.**
- **`train_baselines.py` sits at the repo root** although Phase 1 is complete,
  while the Phase 3 ablations were archived. Arguably inconsistent; left as-is
  because the baselines are the comparison the whole project is structured around.
- **`run_dev.sh`'s SIGINT path is unverified.** SIGTERM shutdown was tested and
  leaves no orphans; Ctrl-C could not be tested from a non-interactive shell.
- **Nothing is pushed.** `main` is 7 commits ahead of `origin/main`.

---

## 10. Change log (appended per feature)

### 2026-10-01 — Queue period filter + expanded contributing reasons

**What changed**

Two features, plus the groundwork each needed.

*1. A period filter on the risk queue.* `GET /api/orders` takes
`last_n_days=N` and keeps only orders inside the trailing N-day window. The
queue gets a **Period** dropdown (All time / 7 / 14 / 30 / 60 / 90 days) in
front of the other filters, and a line under them naming the exact window being
shown.

*2. Contributing reasons went from 5 rule types to 15.* The new ones:
customer/product return rate "above the typical range" (a softer tier below the
absolute 50% one), customer returned N items historically, product returned N
times historically, thin customer history, low-volume product, higher-value
item — plus two explicitly-prefixed **mitigating** factors (customer's or
product's return rate in the bottom quartile) that explain why a low-scoring
order is low. Across the 16,246 seeded orders all 15 fire; orders carry 1–6
reasons each, and the "no significant individual risk factors" fallback drops
from most of the queue to 95 orders.

**Files touched**

```
serving/reasons.py                     rewritten: 15 rule types, train-derived thresholds
serving/config.py                      DISCOUNT_PERCENTILE -> HIGH_/LOW_PERCENTILE
serving/export_seed.py                 load_reason_thresholds(), --reasons-only mode
serving/tests/test_reasons.py          NEW - 16 unit tests for the reason rules
backend/app/services/dates.py          NEW - the shared "what is today" rule
backend/app/services/alerts.py         now uses it instead of its own copy
backend/app/routers/orders.py          last_n_days filter + reported window
backend/app/schemas.py                 PaginatedOrders.reference_date/since_date
backend/tests/test_api.py              +2 tests (16 total)
frontend/src/api/types.ts              PERIOD_OPTIONS, last_n_days, window fields
frontend/src/components/FilterPanel.tsx  Period select + window caption
frontend/src/pages/QueuePage.tsx       feeds the window back into the panel
```

**Decisions**

**"Today" is the latest order date in scope, not wall-clock today.** The order
dates are synthetic and end 2021-11-29, so a window measured from the real
clock would match nothing, every time. `services/alerts.py` had already made
this choice for its trailing 14-day spike window; that logic is now extracted
to `services/dates.py` so the queue filter and the alert window cannot drift
apart. Rejected alternatives: wall-clock now (returns an empty queue — not a
filter, a bug), and a configurable as-of date (more UI for a value nobody would
ever move off the maximum).

**The reference date is resolved against the caller's tenant scope**, the same
way the query itself is, so an analyst's "today" is the newest order *they* can
see. A Platform Admin looking across tenants can therefore have a later "today"
than an analyst inside one — tested explicitly.

**The applied window is returned on the response, not assumed by the UI.**
`reference_date` and `since_date` come back on every queue response, and the
filter panel prints them. A relative window over fabricated dates is exactly
the kind of thing an operator would read as real-time, so the page says what it
actually did.

**Thresholds are computed over training rows that have history, not all of
them.** This fixed a latent flaw in the one pre-existing relative rule: the
product columns are >50% mean-imputed placeholders, so the old discount p75
(17.5749) landed *exactly on the imputation mean*. Taken over rows with real
history it is 17.45, and the other relative thresholds become well-separated
(e.g. product sales p25 = 294 rather than 0).

**The two-tier rate ladder suppresses its relative tier when the quantile sits
above the absolute floor.** On this data the product top quartile is ~38%, below
the 50% "high" floor, so products get a meaningful middle band; the customer top
quartile is ~71%, already inside "high", so the customer middle band would be
unreachable. The suppression is an explicit condition rather than an accident of
ordering — the first draft had it as a plain `elif`, which was a branch that
silently never ran.

**No reason keys off age, year of birth, gender or `premier`.** The first three
are protected characteristics and these strings are the operator's stated
justification for acting on an order; `premier`'s direction of effect was never
measured here, so claiming one would be invention. The model still uses all four
as features — the explanation does not. Pinned by a test.

**Mitigating factors are prefixed and sorted last**, because the queue table
shows `reasons[0]` as its "Top reason" column: a mitigating note must never
displace a risk factor from that slot. Also pinned by a test.

**`export_seed.py --reasons-only`.** Reasons are a presentation layer over
columns the export already reads, so rewording them should not cost a 50-epoch
retrain. The flag rewrites only the `reasons` field of an existing seed file and
asserts per-record alignment against the deterministic order-id sequence — not
just on totals, since a silent misalignment would attach one order's history to
another order's explanation. It also keeps every score bit-identical, which a
rerun cannot promise across torch versions.

**Follow-ups**

- **`backend/orders.db` still holds the old reason text.** The seed JSON was
  regenerated; the database was deliberately *not* reseeded, because it holds
  658 intervention-log rows of demo state. Run `./run_dev.sh --reset-db` (or
  `.venv/bin/python -m backend.scripts.seed_db --force`) to pick up the new
  reasons — that wipes overrides and the audit log.
- **The rule sweep ignores the period filter.** A sweep acts on every pending
  order in the score window regardless of what period the queue is showing. That
  is correct for a score-based rule, but the two surfaces now disagree about what
  "the queue" means, and `SweepConfirm`'s count comes from the unfiltered queue.
  Worth revisiting if rules ever grow a recency condition.
- **No frontend test** covers the period dropdown; verified by build + by
  driving the API directly. The existing frontend-test gap stands.
- The period filter is a *relative* window only. An explicit from/to date range
  would be a small addition to the same endpoint if a demo ever needs to land on
  a fixed historical window.

### 2026-10-01 — Real authentication: accounts, password login, JWT session cookie

**What changed**

The `X-Role` / `X-Actor-Tenant` header simulation is gone. There is a `users`
table, a signup page that creates an account on an existing tenant, a login page
that issues a JWT in an HttpOnly cookie, and a route-guarded app behind it. Every
request now resolves its role and tenant from a database row instead of from a
header the caller wrote itself.

The tenant-scoping logic underneath is **unchanged**. That was the point: it was
already real and tested, and what it lacked was a trustworthy identity to scope
on. `require_role`, `require_tenant_scope` and `get_scoped_tenant_or_none` kept
their bodies; only the two functions that fed them were rewritten.

A fixed Platform Admin account ships with the build and its credentials are
printed on the sign-in page, so the portal is openable by anyone handed the URL.

**Files touched**

```
backend/app/passwords.py        NEW - bcrypt hashing + the anti-enumeration path
backend/app/tokens.py           NEW - JWT issue/decode, cookie set/clear
backend/app/bootstrap.py        NEW - ensure_demo_admin(), one definition, three callers
backend/app/routers/auth.py     NEW - signup / login / logout / me / tenants / demo-credentials
backend/app/deps.py             get_current_user; get_role and get_actor_tenant rewired
backend/app/models.py           User, with a role/tenant CheckConstraint
backend/app/config.py           JWT + cookie settings; DEFAULT_ROLE deleted
backend/app/constants.py        the demo admin constants
backend/app/schemas.py          Signup/Login/Me/DemoCredentials; actor_name removed
backend/app/main.py             auth router, startup admin bootstrap
backend/app/routers/orders.py   actor identity from the session
backend/app/routers/tenants.py  the tenant list is scoped now
backend/scripts/seed_db.py      seeds the demo admin on every run
backend/tests/conftest.py       NEW - logged-in client fixtures
backend/tests/test_auth.py      NEW - 24 tests for the auth system
backend/tests/test_api.py       identity via fixtures; 2 tests deleted
backend/requirements.txt        pyjwt, bcrypt
run_dev.sh                      .env sourcing, dev-secret warning, credentials banner
.gitignore / .env.example       NEW - .env must never be committed
frontend/src/context/AuthContext.tsx   NEW - identity, bootstrap, 401 handling
frontend/src/api/auth.ts, authEvents.ts   NEW
frontend/src/layouts/{AppLayout,AuthLayout}.tsx   NEW
frontend/src/components/{RequireAuth,RequireRole,UserMenu,FullPageSpinner}.tsx  NEW
frontend/src/pages/{LoginPage,SignupPage,NotFoundPage}.tsx   NEW
frontend/src/components/RoleSwitcher.tsx   DELETED
frontend/src/{main,App}.tsx, api/{client,hooks,types}.ts, context/AppContext.tsx
```

**Decisions**

**A JWT in an HttpOnly cookie, not `localStorage` plus a bearer header.** A token
in `localStorage` is readable by any injected script. Everything is same-origin
through the Vite proxy, so there was no cross-site case a bearer header would
have served. The cookie is `SameSite=Lax`, host-only, and `Secure` only when
`RETURNS_DASHBOARD_COOKIE_SECURE=1` — a `Secure` cookie over plain `http://localhost`
is stored but never sent back, which presents as "login works, everything after
it 401s". Setting a `domain=` would break it the same way.

**Role and tenant are re-read from the row on every request, never trusted from
the JWT claims.** A claim is only as fresh as its token, so trusting it would let
a demoted or deactivated account keep its privileges for up to eight hours. The
cost is one primary-key lookup, and FastAPI's per-request dependency cache means
an endpoint using `get_role`, `get_actor_tenant` and `get_current_user` still
performs exactly one. Pinned by two tests: one signs a token with `role: "admin"`
using the real key and asserts it buys nothing, the other deactivates an account
mid-session and asserts the very next request is refused.

**`DEFAULT_ROLE` was deleted rather than repointed.** It made a request with no
headers a silent, valid `ops_analyst` — the largest hole in the old model. Its
absence is the fix: unauthenticated is now 401, which is also what lets the
frontend tell "sign in" apart from "you may not do that".

**Signup picks an existing tenant and cannot create one.** Orders are seeded per
tenant, so a brand-new tenant would open on an empty queue with no alerts and no
baselines — a dashboard that looks broken. Onboarding stays `POST /api/tenants`,
admin-only.

**Signup cannot mint a platform admin, and that is enforced by a `Literal` in the
schema** rather than a hand-written branch, so the refusal is a 422 the framework
produces and cannot be forgotten. Between the two tenant-scoped roles, selection
is open — a deliberate prototype affordance, labelled on the signup form itself.

**`actor_name` was removed from the override and action request bodies.** It was
client-supplied and written into an append-only audit log, which is exactly the
property authentication exists to remove. Verified against the running server: a
request carrying `"actor_name": "Somebody Else"` records the signed-in user.

**bcrypt directly, not passlib.** passlib 1.7.4 is unmaintained and its bcrypt
backend reads `bcrypt.__about__`, removed in bcrypt 4.1; it warns on every
import. `pyjwt` over `python-jose`: no transitive dependencies for HS256, and
python-jose carries CVE-2024-33663/33664. **No `email-validator`** — it pulls
`dnspython`, does DNS deliverability checks inside the request handler, and
breaks `EmailStr` at *import* time when missing, taking the whole app down rather
than one endpoint. A regex is enough for an address we never mail.

**Login tells you nothing about why it failed.** Wrong password and unknown email
return byte-identical 401 bodies, and `verify_password_or_dummy` runs one bcrypt
either way so they take the same time too. Without the dummy hash the missing-user
path returns in microseconds and the endpoint becomes a user-enumeration oracle.

**The admin bootstrap runs at import, beside the existing `_drop_stale_rules_table`
self-heal, not in a lifespan handler.** `TestClient` only runs lifespan events
inside a `with` block, which the fixtures do not use — a lifespan bootstrap would
silently not run under test, and the suite would be exercising a database state
production never has. It also had to run at startup rather than only in the
seeder, because `run_dev.sh` skips seeding entirely when `orders.db` already
exists. This was verified live: the existing dev database grew its `users` table
and admin row on the first reload after the change, with its orders untouched.

**`/api/health` stays open**, because `run_dev.sh` polls it with `curl -sf` and
exits on failure — gating it would report a healthy backend as "backend did not
come up" and point the reader at a log with nothing wrong in it. Pinned by a test.

**Two tests were deleted and twenty-four added.** Deleting tests in a security
change deserves the justification written down: `test_scoped_role_without_a_tenant_is_refused`
drove its case through a blank `X-Actor-Tenant` header, and `test_unknown_role_403`
through a forged `X-Role` header. Neither door exists. What they were really
asserting is covered through the doors that remain — a `CheckConstraint` now makes
"a non-admin with no tenant" a row the database refuses to store, and an
unrecognised role is caught both at login and on every subsequent request.

**`queryClient.clear()` on every identity change, rather than keying caches by
role.** The old cache keys embedded the role, which separated the simulated
identities but would not separate two real users with the same role at the same
tenant. Clearing at the boundary is strictly stronger. Order matters in the 401
handler: the status flips first to disable every mounted query, and only then is
the cache cleared — the reverse would leave enabled queries with no data, refetch
against the dead cookie, and re-enter the handler.

**Follow-ups**

- **`intervention_log` has no `actor_user_id`.** Identity is recorded as a name
  string, so a renamed user rewrites how history reads. A foreign key is the right
  model, but `create_all` cannot add a column to an existing table, so it would
  need either a destructive drop of the audit log or an `ALTER TABLE` repair.
  Deliberately deferred.
- **No frontend tests**, which matters more now than it did: a login screen is the
  one piece of UI where a silent failure is a security problem. The checks in this
  entry were done by hand against the running server.
- **`backend/requirements.txt` describes the backend only.** The ML pipeline's
  dependencies (torch, PyG, pandas, the gradient-boosting libraries) are declared
  nowhere, so `pytest serving/tests` is not reproducible from a clean clone.
  Unrelated to this change; worth its own `requirements-ml.txt`.
- The two new auth libraries are version-bounded while the original six lines stay
  unpinned. Asymmetric on purpose — a major bump in an auth library is a behaviour
  change — but the file should eventually be pinned throughout.

### 2026-10-01 — Fix: `/api/alerts` returned 500; smoke coverage for every read endpoint

**What changed**

`GET /api/alerts` had been returning a 500 since the period-filter change
earlier the same day. Extracting the trailing-window logic into
`services/dates.py` removed `_recent_window` from `services/alerts.py` along
with its `datetime` imports — and took `from sqlalchemy import func` with them,
which the cohort count/average query on line 43 still used. A one-line
`NameError`, reaching the browser as "internal server error".

Restored the import, then closed the reason it survived: **nothing in the suite
had ever called the endpoint.** Six read endpoints had zero coverage —
`/api/alerts`, `/api/audit-log`, `/api/meta`, `/api/roles`, `/api/tenants` and
`/api/reporting/baseline-vs-actual` — as did `PATCH /api/orders/{id}/actions/{log_id}`
and `POST /api/tenants`.

**Files touched**

```
backend/app/services/alerts.py   the restored import
backend/tests/test_api.py        +16 tests (61 backend, 77 with serving/)
```

**Decisions**

**A parametrized smoke test over every read endpoint, asserting a plain 200.**
It is the cheapest possible guard and it catches the entire class this bug
belongs to — a dropped import, a typo in a path, a dependency that stopped
resolving. Run for an analyst and again for the platform admin, because the
admin path is the one that runs unscoped and loops over every tenant rather
than filtering to one. Verified by reintroducing the missing import and
confirming three tests fail.

**Plus real behavioural tests where a 200 proves little**: a seeded cohort with
a 0% baseline and twenty all-returned orders must actually be flagged, with the
right severity, attributed to the right tenant and to no other; recording an
action outcome must close the order; onboarding a tenant must be refused for an
analyst and must 409 on a duplicate.

**Follow-ups**

- The lesson generalises past this endpoint: **the suite tested the paths the
  features were written against, not the surface the app exposes.** The smoke
  list is now the inventory, and a new route should be added to it when it is
  added to a router.
- Still no frontend tests, so the equivalent gap remains on that side — an
  alerts page that renders an error banner looks much like one with no alerts.

### 2026-10-02 — Frontend accessibility, URL state and locale pass

**What changed**

A review of the whole frontend against the Vercel Web Interface Guidelines,
then the fixes. Four clusters, in rough order of how much they mattered:

**1. Twenty form controls had no accessible name.** `FilterPanel` alone had
eight `<label>` elements sitting next to eight controls with no `htmlFor`/`id`
pairing — visually identical to a working label, and inert: nothing announced,
clicking the text did nothing. The same pattern was in both order-detail forms,
`AuditLogTable` (two selects with no label at all), `AlertsPage`,
`HistoryTimeline` and `ReportingPage`. All now paired through `useId()`.

**2. No page kept its state in the URL.** The queue read `country` and
`product_type` from the query string exactly once at mount, then held
everything in `useState` — so a filtered queue could not be shared, bookmarked
or backed out of, and the link an analyst sent showed the recipient the
unfiltered queue. Queue filters, queue pagination, the alerts threshold, the
audit-log filters and pagination, and the reporting cohort now all live in the
query string via a new `lib/urlState.ts`.

**3. `SweepConfirm` claimed to be a dialog without being one.** It carried
`role="alertdialog"` on a plain `<div>`: focus stayed behind it, Tab walked out
into the page underneath, Escape did nothing. This guards the only irreversible
action in the app. Now a real `<dialog>` opened with `showModal()`, which
supplies the focus trap, the inert backdrop and Escape; focus lands on Cancel
rather than the destructive button, and returns to the opener on close.

**4. Dates and numbers were formatted by hand.** Raw `order_date` strings were
printed as stored and timestamps went through bare `toLocaleString()`. All of
it moved to `Intl` behind `lib/format.ts`. `formatDate` deliberately splits the
ISO string rather than calling `new Date(value)`: the date-only form parses as
UTC midnight and renders as the previous day anywhere west of Greenwich.

Smaller, by theme:

- **Copy.** `"filter(s)"`, `"order(s)"`, `"rule(s)"` → a `pluralize()` helper.
  Raw wire tokens (`pending`, `high`, `intervention_action`) were being printed
  as UI text; they now go through label maps in `api/types.ts`. Error messages
  state a next step rather than only the problem. Straight quotes → curly.
- **The `AuditLogTable` 403 message named "Ops Manager"**, a role that has not
  existed since the rename to Tenant Admin. Built from `ROLE_LABELS` now, so it
  cannot drift again.
- **Empty and error states.** Zero audit entries rendered a header over an
  empty `<tbody>`; `ReasonsList` rendered a bare `<ul>`; `OrdersTable` rendered
  a blank cell when `reasons` came back empty; `createTenant` failures were
  swallowed entirely, so a duplicate name 409'd and the form just did nothing.
- **Forms.** Submit buttons no longer disable on empty input — they validate on
  submit, put the message beside the offending field, and focus it. A disabled
  button states no reason. `beforeunload` guards the override and signup forms.
- **`PrototypeBanner` read `sessionStorage` inside a `useState` initializer.**
  That access *throws* when a browser blocks site data, taking down the whole
  tree rather than degrading to the default. Now behind `lib/storage.ts`.
- **The chart ignored dark mode.** Recharts takes colours as props, so Tailwind
  `dark:` variants could not reach it: light-mode axis text and a white tooltip
  on a dark page. Colours now come from CSS custom properties that swap with
  the scheme, and the chart gained a table view.
- **Globals.** Skip link and a focusable `<main>`; `touch-action: manipulation`;
  a `prefers-reduced-motion` block; `theme-color` meta per scheme;
  `env(safe-area-inset-*)` on the shell; `h-dvh` over `h-screen`; `scope` on
  every `<th>` and a `sr-only` `<caption>` on every table; `translate="no"` on
  order IDs and credentials.
- **`autoFocus` on the login email field fired on phones too**, raising the
  keyboard over the page before it could be read. Now gated on `(pointer: fine)`.

**Files touched**

```
frontend/index.html                        theme-color, viewport-fit
frontend/src/index.css                     reduced motion, touch-action, focus-visible, chart tokens
frontend/src/lib/                          NEW - format, storage, controls, urlState,
                                           useUnsavedChanges, useDesktopAutoFocus
frontend/src/api/types.ts                  label maps for status, outcome, severity, sort
frontend/src/layouts/{App,Auth}Layout.tsx  skip link, main landmark, safe areas
frontend/src/pages/*.tsx                   all 7
frontend/src/components/*.tsx              13 of 15 (ScoreBadge, ColdStartBadge unchanged)
```

**Decisions**

**A shared `lib/controls.ts` rather than fixing each button.** The primary
button had no hover state in six places because the class string had been
copy-pasted six times. One vocabulary means an affordance change is one edit;
it is also what made the Windows-dark-mode select fix a single line.

**`useUrlState` takes module-scope `read`/`write` functions.** It needs stable
references, and forcing the codec out of the component body also makes the
URL contract for each page readable in one place. Defaults are written as
*absent* params, so an untouched queue has a clean URL and only deviations are
visible in it.

**Validated the chart palette rather than picking colours.** Two series on one
axis, taking categorical slots 1 and 2 from the reference palette, stepped
separately for each surface and run through the validator: worst-pair CVD ΔE
24.7 light / 26.8 dark, normal-vision 33.6 / 31.8, both ≥ 3:1 against their
surface. The baseline stays dashed — secondary encoding, so the two series
separate without relying on hue at all.

**Kept the review's own finding about `preconnect` unfixed, on purpose.** The
API is same-origin and there is no asset CDN, so a preconnect hint would be
decoration. Said so in a comment in `index.html` instead.

**Verification**

`tsc --noEmit` and `vite build` clean; 61 backend tests still passing; both
servers started and the queue, audit-log and alerts endpoints exercised with
the exact query strings the new URL state emits (200 on each, filters applied).

**Follow-ups**

- **The in-app navigation half of the unsaved-changes guard is missing.**
  `beforeunload` covers tab close and reload; intercepting a route change needs
  react-router's `useBlocker`, which requires a data router — the app mounts a
  plain `BrowserRouter`. Swapping it is the real fix.
- **Still no frontend tests**, and this change touched 28 files of UI. Every
  claim above was verified by typecheck, build, and the API calls the new URL
  state produces — not by rendering a component and asserting on it. The label
  associations and the dialog focus behaviour in particular are exactly the
  kind of thing that regresses silently.
- `OrdersTable` caps at 25 rows a page so virtualization is not needed yet; if
  `page_size` ever grows past ~50 it will be.
- The queue's `page_size` is fixed at 25 and is the one piece of view state not
  in the URL.

### 2026-10-02 — Visual design pass: one hue, a real type scale, a queue that has an opinion

**What changed**

The interface had no point of view. Three measurements made the case:

- **Eight accent hues, 180 colour utilities.** The risk scale (red/amber/emerald)
  was competing with a teal slider, a violet cold-start chip, a sky-blue one, an
  amber banner and a blue link — often inside the same table row. When everything
  is coloured, the colour that encodes risk means nothing.
- **139 of 149 type sizes were `text-xs` or `text-sm`.** 93% of the UI was one of
  two sizes. The risk score — the number the product exists to produce — was 12px,
  *below* the tracked-out uppercase column heading above it in the hierarchy.
- **26 of 30 border-radii were the same 4px `rounded`**, on chips, fields, modals
  and cells alike.

Plus the template chrome: all-caps tracked-out column heads in 6 files, `·`-joined
meta strings, `→` appended to 6 labels, and `system-ui` — the absence of a
typographic choice rather than a choice.

**The governing rule is now: colour is risk.** The chrome is achromatic end to
end — rules, type, controls, focus, nav, links (underlined, not blue). The only
hue in the interface is a single-hue risk ramp, so a red row means something.
Errors and the destructive sweep button take the top of that same ramp, because
"this failed" and "this is dangerous" are the same alarm; success and warnings
are achromatic, because they are not.

**Risk is a three-step traffic light: green, yellow, red.** I first built a
single-hue ramp instead, on the argument that a continuous score should read as
one scale and that red/green is the worst pair for colour-vision deficiency.
Overruled — an ops audience reads a traffic light instantly and the convention
is worth more than the purity. Built it properly rather than reluctantly:

- The three colour steps now use the *same* thresholds as the tier words
  (<0.40, <0.70, else), so the colour and the word beside it can never
  disagree. They were previously two separate scales — five equal colour bands
  against three uneven word bands — so a 0.62 could render in the fourth of
  five colours while reading "medium".
- Green and red are separated by **lightness** (OKLCH L 0.60 vs 0.47), not hue
  alone. That is what lifts the worst all-pairs CVD separation to ΔE 8.4 light
  / 9.0 dark, clear of the 8.0 floor. The naive bright green/red pairing scored
  7.2 and would have failed.
- **Two roles per step**, because one set cannot do both jobs on white.
  `--risk-N` is for marks (histogram bars, chips) and is tuned for
  discrimination. `--risk-N-text` is for text and is tuned for legibility — all
  three clear 4.5:1.

The honest caveat, recorded because it is a real limit: pushing all three text
steps to 4.5:1 on a white surface compresses green and yellow to a CVD ΔE of
2.8, below any floor. That is acceptable *only* because colour never carries
the information alone — every call site prints the score and the tier word next
to it. A future call site that uses the text colour as the sole signal would be
a bug, and the token block in `index.css` says so.

**Type.** Barlow, with its Semi Condensed width for column heads and metadata,
plus IBM Plex Mono for order and customer refs. Five real steps (11/13/15/20/28)
replacing the effective two. The condensed width is what lets column heads sit in
sentence case at a readable size instead of being tracked out into caps for
density.

**The queue got a distribution strip**, replacing the Min/Max score boxes. A
number typed into a box says nothing about the population it cuts into; the strip
shows where the orders actually are, with the score window drawn on it and the
excluded bands dimmed rather than hidden. The real data is a bathtub — 2,256
orders under 0.05 and 1,071 above 0.95, flat in between — which is a genuinely
useful thing for an operator to see before they pick a threshold.

The control under it is the existing dual-thumb `ScoreRangeSlider` on the same
axis, not a bespoke drag brush: it already has full keyboard support, and
reimplementing that would have meant getting it wrong.

**The queue table's hierarchy is inverted from what it was.** Score is now the
largest thing in the row, tabular, on the ramp. Column heads are 11px condensed
sentence case. The Tenant column is hidden for anyone who can only see one tenant
— it was repeating the same word down every row — and the reason column, which is
*why you would act*, takes the width that frees up instead of truncating at
`max-w-xs`. The sidebar went 256px → 208px.

**Files touched**

```
backend/app/routers/orders.py      _filtered_orders() extracted; /orders/score-histogram
backend/app/schemas.py             ScoreHistogram, ScoreHistogramBucket
backend/tests/test_api.py          +6 tests (69 total)
frontend/index.html                Barlow + IBM Plex Mono, preconnect, theme-color
frontend/src/index.css             the token system; -33% CSS (30.6kB -> 20.6kB)
frontend/src/lib/{controls,risk}.ts  achromatic vocabulary; the one place hue is allowed
frontend/src/components/RiskDistribution.tsx   NEW
frontend/src/{pages,components}/   28 files swept onto tokens
```

**Decisions**

**The histogram endpoint takes every queue filter except min/max score.** Those
two are the selection drawn *on* the distribution, so bounding the distribution
by them would collapse the strip onto the selection and make the window
meaningless. The filter set is extracted into `_filtered_orders()` and shared with
the list endpoint, so the strip can never describe a different population than the
table beneath it — which is what the new tests assert.

**Tests assert invariants against `/api/orders`, not fixed scores.** The first
draft pinned the seeded order to 0.90/pending and passed alone but failed in the
suite: earlier tests override scores and run sweeps. What matters is the
relationship between strip and table, and that holds in any state.

**Sentence case throughout.** The two rulesets in play disagree — the web
interface guidelines ask for Chicago Title Case on headings and buttons, the
design direction asks for sentence case. Sentence case is quieter, which suits an
operational tool. Picking one and applying it everywhere mattered more than which.

**The chart stayed achromatic.** Its two series are not risk scores, so under
the rule they get no hue; they are told apart by form instead — a solid bar for
what happened, a dashed rule for the baseline. That also separates them for a
colourblind reader and in print.

**Errors are on an `--alarm` token, not on the risk scale.** Same pixels as the
red step, a separate name, so a failed request does not read in the source as
though it were "high risk" — and so the two can diverge later without a
find-and-replace.

**Verification**

69 backend tests passing (6 new). `tsc`, `vite build` and `oxlint` clean — the two
remaining oxlint warnings are the pre-existing `only-export-components` ones in
the context files. Both servers started; the histogram endpoint was exercised
against the real seeded data and its distribution printed and eyeballed. Zero raw
Tailwind colour utilities remain in `src/`.

**Follow-ups**

- **Nobody has looked at this in a browser.** Verified by typecheck, build, lint
  and API responses only — there is no screenshot in the loop and no frontend
  tests. A mechanical regex swept 28 files; it already produced one real bug (the
  rule Active/Inactive toggle collapsed to identical styling for both states,
  caught by a leftover-colour grep). Others may be sitting in pages the grep had
  no reason to flag.
- **The green/yellow/red steps have been validated numerically but not looked
  at.** Contrast ratios and CVD deltas say they work; whether the yellow reads
  as "caution" rather than "mustard" against this particular panel grey is a
  judgement no validator makes.
- Scope was tokens + queue page. Alerts, Admin, Order detail and the auth pages
  inherited the token system but keep their old structure — their layout has not
  been designed, only recoloured.
- The queue's two-line-row alternative was rejected for density, but the reason
  column still `line-clamp-1`s. A row that expands on focus would show the full
  reason without costing rows.
- `/reporting` is still route-disabled, so the restyled chart remains unreachable.
- Fonts load from Google Fonts. For an internal tool that should be self-hosted.

### 2026-10-02 — Contrast and layout corrections to the design pass

**What changed**

A third guidelines review of the redesign, and the fixes. Most findings were my
own, introduced by the previous entry.

**I validated the palette against the wrong surface.** The mark steps were run
against `#ffffff` and recorded at 2.49:1, but the histogram renders on
`--panel`. The real figure is 2.28:1. The token comment stated the wrong
number; it now states the right one and says which surface it refers to.

That one is **not fixed, deliberately, and the reasoning is in the token
block**: every step darker costs CVD separation, and a yellow dark enough to
clear 3:1 on a light surface is brown — which loses the traffic light the scale
exists to be. Two candidate re-tunes were measured and both made it worse
(green↔red CVD fell to 7.0–7.9 while the yellow still only reached 2.76–2.88).
The mark floor's documented relief applies instead, and is real here: bars sit
on a labelled 0–1 axis so position already identifies the band, the strip is
`aria-hidden` behind an sr-only count, and every score prints its tier in words.

**Text contrast was measured against the wrong surface too, and that one is
fixed.** `--risk-1-text` was 4.38:1 on `--panel` — under AA — which a queue row
hits on hover. All three text steps were re-tuned to clear 4.5:1 against both
`--paper` and `--panel`, in both modes.

**Form fields had no visible boundary.** `--rule` is 1.33:1, right for a table
divider and invisible as an input edge, which WCAG 1.4.11 wants at 3:1. Added
`--rule-strong` (3.37:1 on paper, 3.09:1 on panel, both modes) and pointed
`CONTROL`, `BUTTON_SECONDARY` and `BUTTON_SMALL` at it. Dividers keep `--rule`.

**The destructive sweep button was 3.68:1 in dark mode** — `text-white` on an
`--alarm` that is lighter there. Now `text-paper`: 7.93:1 light, 5.37:1 dark.

**`line-clamp-1` on the reason column was doing nothing.** I had removed
`max-w-xs` to give the column its width back and replaced truncation with a
class that needs a width constraint I had just deleted — under the default auto
layout a cell sizes to content regardless. The table is `table-fixed` now with
stated column widths, so the reason column takes the remainder and actually
clamps; the order link and tenant cell truncate rather than clip.

Smaller: the strip's heading was an `<h2>` sibling of the queue's own `<h2>`
when it is a section of it (now `<h3>`); its sr-only summary was not a live
region, so moving the window announced nothing (now `role="status"`); the 13
bare `rounded` the sweep left behind now follow the declared scale (2px
interactive, 4px floating surface, none on rows — 16 and 12 of them, nothing
else); and the font stylesheet is preloaded.

**Files touched**

```
frontend/index.html                      preload the font stylesheet
frontend/src/index.css                   --rule-strong, re-tuned text steps, corrected comment
frontend/src/lib/controls.ts             interactive borders -> --rule-strong
frontend/src/components/OrdersTable.tsx  table-fixed + column widths
frontend/src/components/SweepConfirm.tsx text-paper, radius scale
frontend/src/components/RiskDistribution.tsx  h3, role="status"
+ 9 files for the radius scale
```

**Decisions**

**Email placeholders keep `you@example.com` without a trailing ellipsis.** The
guideline asks for both an example pattern and a trailing `…`; appending one to
a complete example address implies truncation that is not there. Taking half
the rule on purpose.

**Sentence case stays.** These guidelines ask for Chicago Title Case on
headings and buttons; the design direction asked for sentence case and that is
what the interface uses throughout. Recorded as a standing deviation rather
than left to look like an oversight.

**Verification**

Every token pair re-measured from the live CSS rather than from memory: all
text ≥4.5:1 and all interactive borders ≥3:1, in both modes, against both
surfaces. 69 backend tests passing; `tsc`, `vite build` and `oxlint` clean.

**Follow-ups**

- **Still not looked at in a browser.** `table-fixed` with hand-picked column
  widths is exactly the kind of change that is correct in principle and wrong at
  some viewport — the widths total 672px before the reason column, so a narrow
  window will lean on the container's horizontal scroll.
- True `<link rel="preload" as="font">` needs the woff2 files served from this
  origin. Self-hosting remains the follow-up, and is what an internal tool
  should do regardless.

### 2026-10-06 — Escalation: an analyst-to-tenant-admin hand-off

**What changed**

A sixth intervention action, `escalate`, and a tenant-admin-only queue of the
orders it produces. An Ops Analyst escalates from an order's page with a note
saying why; the order appears under **Escalations** for that tenant's admin and
stays there until someone records an outcome against it.

**Files touched**

```
backend/app/constants.py              `escalate` + HANDOFF_ACTION_TYPES
backend/app/services/escalations.py   NEW - the query over intervention_log
backend/app/routers/escalations.py    NEW - GET /api/escalations
backend/app/schemas.py                EscalationOut
backend/app/main.py                   router included
backend/tests/test_api.py             +4 tests (79 backend, 91 with serving/)
frontend/src/api/types.ts             action + label + EscalationOut
frontend/src/api/hooks.ts             useEscalations
frontend/src/components/EscalationsTable.tsx   NEW
frontend/src/pages/EscalationsPage.tsx         NEW
frontend/src/App.tsx                  route behind RequireRole
frontend/src/components/NavSidebar.tsx         nav link for tenant_admin+
```

**Decisions**

**No `escalations` table.** An escalation *is* an intervention action, and
`intervention_log` is already the append-only record of what people did — so
this is a query over that log, not a second copy of the same fact. A separate
table would have to be kept in step with the log, and the two could disagree
about whether an order was ever escalated. Open versus resolved is the log
row's own `outcome`, which means `GET /api/escalations` is a read and the
feature adds no new write path at all.

**Resolved through the existing `PATCH /orders/{id}/actions/{log_id}`.** An
escalation closes the way every other logged action closes. Inventing a
`POST /escalations/{id}/resolve` would have been a second way to write the same
column, and the order would then have two notions of "closed".

**Keyed on `log_id`, not `order_id`.** The same order can be escalated more
than once over its life — raised, resolved, and raised again on new
information. An outcome is recorded against one particular hand-off, so the
row identity has to be the log entry.

**Gated at `tenant_admin`, and the route is gated to match.** The analyst
raises escalations but does not work the queue of them; that asymmetry is the
entire point of a hand-off. The nav link and the `/escalations` route sit
behind the same `RequireRole` the endpoint enforces, so an analyst who types
the URL gets the explanatory panel rather than a page of 403s.

**It is also available as a rule action.** `escalate` went into `ACTION_TYPES`,
which the rule editor already maps over, so a tenant can auto-escalate a score
band without any further work. The table distinguishes the two: a row raised by
a sweep shows "Automated rule" where a manual one shows the analyst's name.

**Follow-ups**

- An analyst can still resolve their own escalation, because
  `PATCH /orders/{id}/actions/{log_id}` is gated at `ops_analyst`. Arguably it
  should require `tenant_admin` when the action being closed is a hand-off —
  `HANDOFF_ACTION_TYPES` exists in constants.py so that check has somewhere
  obvious to live. Left alone for now rather than tightening an endpoint that
  predates this feature.
- The queue is unpaginated. Fine at prototype volumes; it is the same shape as
  the alerts list, which has the same limitation.

### 2026-10-08 — Dropped "RTO" for plain returns language, and the India target

**What changed**

Two things, one small and one sweeping.

**Escalation is no longer available to automated rules.** `RULE_ACTION_TYPES`
is `ACTION_TYPES` minus `HANDOFF_ACTION_TYPES`, and the two rule-validation
sites and the rule editor use it. Escalating stays a manual action.

**The product is a returns risk engine, not an RTO engine.** RTO (return to
origin) is India-specific logistics vocabulary, and the India D2C target is
dropped — so every "RTO" in the project became returns language, and the India
references went with it. `Context/` and `archive/` were left untouched by
decision: the first holds the PRD and papers as they were given, the second is
a record of what was tried.

**Files touched**

```
backend/app/constants.py          RULE_ACTION_TYPES; demo admin renamed
backend/app/routers/rules.py      validates against RULE_ACTION_TYPES
backend/app/bootstrap.py          migrates the old demo-admin row
backend/app/config.py             RETURNS_DASHBOARD_* vars, returns_session cookie
backend/app/passwords.py          RETURNS_DASHBOARD_BCRYPT_ROUNDS
backend/app/main.py               app title
backend/app/services/alerts.py    wording
backend/tests/conftest.py         renamed env vars
backend/tests/test_api.py         +1 test (77 backend, 92 with serving/)
build_features.py                 India order-feature hook removed
build_graph.py, train_gnn.py      edge-feature wording neutralised
profile_data.py, eval_harness.py, train_baselines.py, serving/config.py   wording
run_dev.sh, .env.example          renamed env vars
data_profile_report.md            regenerated against data/clean
frontend: types.ts, RulesForm, AppContext, PrototypeBanner, NavSidebar,
          AuthLayout, AlertsPage, ReportingPage, index.html
docs/checkpoint_phase0_phase3.md  title, PRD reference, future work
```

**Decisions**

**Rules cannot escalate, by construction rather than by convention.** A sweep
that escalated a whole score band would hand the tenant admin a queue nobody
could work — the opposite of what a hand-off is for. Deriving the rule
vocabulary from the action vocabulary means a future hand-off action is
excluded automatically, instead of relying on whoever adds it to remember.

**Identifiers were renamed too, not just prose.** The env vars, the session
cookie and the localStorage keys all carried `rto`. Renaming the cookie signs
everyone out once; renaming the env vars would break an existing `.env`, except
there is no `.env` on this machine to break. The alternative — a clean-looking
codebase whose config still says RTO — would have left the rename half-done in
exactly the place someone looks when something is misconfigured.

**The legacy strings are deliberately *not* renamed.** `AppContext.LEGACY_KEYS`
and `constants.LEGACY_DEMO_ADMIN_EMAIL` hold the old `rto-*` names because
their whole job is to match what is already in a browser or a database and
retire it. A blanket find-and-replace renamed them on the first pass, which
silently turned the cleanup into a no-op; both now carry a comment saying why
they are exempt.

**The demo admin's row is moved, not duplicated.** `ensure_demo_admin` looks up
by email, so changing the constant would have created a second admin and left
the old one working under an undocumented password. It now renames the existing
row and re-hashes it. Verified against a copy of the live database: one admin
row, new credentials accepted, old ones refused.

**`data_profile_report.md` was regenerated rather than edited.** It turned out
to be a profile of the India synthetic set — 237k events, 277,777 customers —
while §3 of this log cited it as the Phase 0 profile of the ASOS tables. Rerunning
`profile_data.py data/clean` replaced it with a report of the data the project
actually uses (1,343,912 events, 764,725 customers), which removed the India
content and corrected the citation in one step.

**The India order-feature hook came out of `build_features.py`; the generic
edge-feature path stayed.** The hook loaded a side file that only the archived
generator ever wrote. The `ord__*` plumbing in `build_graph.py` and
`train_gnn.py` is not India-specific — it is how any order-level field would
reach the model, which the input contract calls for — so it kept its code and
lost its India-flavoured comments. Nothing produces `ord__` columns today and
the comments now say so.

**`convert_cod_to_prepaid` stayed.** Cash on delivery is not India-only, and
the string is stored in `intervention_log` and `automated_rules` rows, so
renaming it would orphan logged actions and any rule using it.

**Follow-ups**

- The repo directory is still `RTO_for_UGP`, and the regenerated profile report
  prints that path. Renaming the working directory was out of scope for a
  find-and-replace; it would want doing deliberately, with the remote updated.
- `archive/` still contains the India work by decision. Anyone grepping the
  whole repo will find it there; nothing outside `archive/` points at it any
  more.

### 2026-10-08 — A landing dashboard, and what to do with actions that never resolve

**What changed**

A new `/dashboard` page, now the post-sign-in landing for every role, with
`/queue` one click away in the sidebar. Two sections and one new read endpoint.

*Section A, "What came in"* — orders over a selectable period (the same six
`PERIOD_OPTIONS` the queue uses): orders in, cold-start count and share, and a
three-segment risk-mix bar on the existing `<0.40 / <0.70` breaks.

*Section B, "What we did"* — all time, no period filter: orders cleared for
delivery, orders flagged for manual review, orders escalated and still open, and
**Open interventions** (a count of `intervention_log` rows with
`outcome='pending'`) with a per-type breakdown beneath it.

**The design problem this feature is really about.** Of the seven actions, three
resolve inside the system — `proceed_with_delivery` *is* the decision,
`flag_for_manual_review` routes to a queue you can see, `escalate` routes to the
Escalations page. The other four (`call_customer`, `send_confirmation_sms`,
`send_reminder_email`, `convert_cod_to_prepaid`) wait on a customer this
prototype has no channel to hear from, and the project's scope ends at "the
action was logged". The data model turned out to have anticipated this already:
every action is born `outcome='pending'` and `OUTCOMES` already contains
`no_response`. So nothing new was invented — the page surfaces
`outcome='pending'`, which is the query `services/escalations.py` was already
running for one action type.

**Files touched**

```
backend/app/services/dates.py          MAX_PERIOD_DAYS moved here from routers/orders.py
backend/app/services/escalations.py    ESCALATION_ACTION / OPEN_OUTCOME promoted;
                                       count_open_escalated_orders() added
backend/app/services/dashboard.py      NEW - the five queries
backend/app/routers/dashboard.py       NEW - GET /api/dashboard
backend/app/schemas.py                 Dashboard* models
backend/app/main.py                    router registered
backend/app/routers/orders.py          imports MAX_PERIOD_DAYS instead of defining it
backend/tests/test_api.py              +10 tests, +1 smoke endpoint (104 total with serving/)
frontend/src/api/types.ts              Dashboard* interfaces
frontend/src/api/hooks.ts              useDashboard; 4 mutations now invalidate ["dashboard"]
frontend/src/components/StatTile.tsx   NEW - the <dl> pair lifted out of RiskDistribution
frontend/src/components/RiskMixBar.tsx NEW - the page's only colour
frontend/src/pages/DashboardPage.tsx   NEW
frontend/src/App.tsx, NavSidebar.tsx, LoginPage.tsx, SignupPage.tsx   route + redirects
```

**Decisions**

**The period governs the orders section and not the actions section.** Order
dates are synthetic and end 2021-11-29, while `intervention_log.created_at` is
real wall-clock time — currently 2026. A single "last 7 days" control over both
would have measured two windows five years apart and labelled them identically.
The actions section is all-time and says so, in a marker sitting exactly where
the other section's dropdown sits, so nobody has to hunt for which window a
number covers.

**An action count is not an order count, and the response shape says so.** The
first three tiles are `COUNT(DISTINCT order_id)`; `open_actions` counts log
rows. One order can carry several actions, so the two are never summed.
`reference_date`/`since_date`/`last_n_days` are nested **inside** `orders`
rather than on the envelope, so there is nothing at the top level that could be
read as applying to both halves. In the UI the separation is mechanical, not
just visual: one `<dl>` per section and never a tile from each in the same one,
a surface change between them, and a unit word in every label.

**The action tiles read `intervention_log`, never `order_status.status`.** That
column is last-write-wins across five writers, so an order cleared for delivery
and later flagged reports only `actioned` — the latest thing that happened to
it, not the record of what was done. Pinned by a test that logs both actions on
one order, asserts the status is a single string, and asserts both tiles still
count it.

**`total_actions_logged` is computed on the server, not inferred from four
zeros.** A tenant whose only logged action was a phone call moves none of the
four tiles while its log is plainly not empty, so the UI cannot tell "nothing
has happened" from "nothing that happened lands in these tiles". It costs no
extra query — it rides along as a second aggregate in the pass that was already
grouping by action type. It also earns a visible place: the Open interventions
tile prints "of N logged all time", which is what stops the page reading as
dead when work has been done that these four tiles do not cover.

**No synthetic activity was seeded; `seed_db.py` is untouched.** The demo
database holds three intervention rows against 16,246 orders, so Section B
reads near-zero and will keep doing so until somebody works the queue. That is
the honest state of a prototype whose subject is what a team actually did, and
fabricating history would have made a demo of the one thing on the page that
cannot be faked. The empty states were therefore designed first rather than
bolted on, and the em dash is reserved strictly for "the number has not
arrived" — a tile whose data has loaded prints `0`, never `—`.

**A hindsight panel was designed and dropped.** It would have compared the
observed 2021 return rate of flagged against unflagged orders (or by risk band:
83.2% / 50.8% / 13.0%, which is a genuinely strong result). It is not on the
page because it reads as proof that interventions prevented returns, and those
returns predate the tool by five years. `is_returned_ground_truth` is read
nowhere in this feature.

**A top-level router rather than `/orders/dashboard`.** A route under `/orders`
must be declared above `/{order_id}` or its path segment parses as an order id —
the footgun already documented for `score-histogram`. A separate prefix removes
the constraint instead of adding a second thing to remember.

**The page is open to any authenticated role**, although `/api/escalations` is
gated at `tenant_admin`. Working the hand-off queue is the tenant admin's job; a
scalar count of a tenant's own open escalations is not that queue, and the
analyst who raised them already sees each one in its order's history.

**Verification**

104 tests pass (92 before: 10 new dashboard tests, plus the analyst and
platform-admin cases the parametrized smoke inventory picks up for free). `tsc`,
`vite build` and `oxlint` clean, with only the two pre-existing
`only-export-components` warnings.

**Driven in a real browser**, which the last two visual passes were not — with
throwaway Playwright in a scratchpad venv, never added to the project:
sign-in lands on `/dashboard`; the period dropdown writes `?last_n_days=14`,
moves Section A to 3,756 orders and its provenance line to "Nov 16 – Nov 29,
2021" while Section B does not change or flash; a hand-edited
`?last_n_days=9999` degrades to All time rather than erroring; a brand-new
tenant with no orders renders both empty states and a 200, not a 500; and
logging a flag from an order page moves the dashboard from 0 to 1 flagged, 0 to
1 open and 2 to 3 logged with no manual refresh. Zero page errors throughout.
The SQL was counted rather than assumed: **5 statements per request**, none
inside a loop.

Two bugs were found this way and fixed — a JSX newline that swallowed the space
before an em dash, and the missing "of N logged all time" line.

**Follow-ups**

- **`RISK_BREAKS` is duplicated** across `services/dashboard.py` and
  `lib/risk.ts`, with a comment in each pointing at the other. The UI must
  colour a band the same way the API counted it, and a Python module and a TS
  module have no mechanical link.
- **Section B stays near-zero** until the demo database accumulates real use.
  That is correct, and it does mean a fresh clone shows a dashboard whose
  right-hand half is a sentence rather than numbers.
- One `flag_for_manual_review` on `DEMO-ORD-010209` was logged by the browser
  verification and left in place, because `intervention_log` is append-only by
  design and hand-deleting from it is exactly what the model forbids. The
  throwaway "Empty Brand" tenant created for the empty-state check was removed
  (it had no orders, users, rules or log rows).
- The breakdown lists only action types with a non-zero count, so its height
  changes as counts appear. Seven rows of zero was the worse option.
- Still no frontend tests. This page was driven by hand through a real browser
  rather than asserted on, so the empty-state branches in particular are the
  kind of thing that regresses silently.

### 2026-10-09 — Dashboard: bigger type, and the prose behind "i" buttons

**What changed**

The dashboard's numbers and text went up one step each on the existing scale,
and its two explanatory paragraphs moved into disclosure buttons beside the
section headings.

Sizes, all existing tokens — no new steps were invented:

| | was | now |
|---|---|---|
| Page title | `text-title` 20px | `text-display` 28px |
| Stat values | `text-title` 20px | `text-display` 28px |
| Section headings | `text-head` 15px | `text-title` 20px |
| Stat labels and hints | `text-meta` 11px | `text-body` 13px |
| Breakdown rows, empty states | `text-body` 13px | `text-head` 15px |
| Risk legend counts | `text-body` 13px | `text-head` 15px |

The risk bar went 8px to 12px tall so it still carries weight against the
larger type.

**Files touched**

```
frontend/src/components/InfoButton.tsx   NEW - the disclosure
frontend/src/pages/DashboardPage.tsx     type scale + the two buttons
frontend/src/components/StatTile.tsx     value -> text-display, label/hint -> text-body
frontend/src/components/RiskMixBar.tsx   taller bar, legend up one step
```

**Decisions**

**A disclosure, not a tooltip.** Tooltips are hover-only: they never existed on
touch and were invisible from the keyboard. `InfoButton` is a real button with
`aria-expanded`/`aria-controls`, closes on Escape and on a click outside, and
returns focus to itself on Escape so the keyboard path does not dead-end.
Verified in a browser through all four paths.

**The applied window stayed on the page; only its explanation moved.** The old
provenance line did two jobs — "Showing Nov 16 to Nov 29, 2021" (what the
filter actually did) and "these dates are synthesized, a period counts back
from the newest order" (why). The first is a fact the page is obliged to state;
the whole point of returning `reference_date`/`since_date` on the response was
that a relative window over fabricated dates must not be left to assumption.
So the line now reads only the window, and the explanation is behind the
button.

**Empty-state copy stayed inline.** It is the content of the section in that
state, not description of it — putting "No actions logged yet" behind a button
would leave an empty panel explaining nothing.

**The "i" is round, which breaks the radius scale** in `lib/controls.ts` (2px
interactive / 4px floating / none on rows). A circular info affordance is a
strong enough convention to be worth the deviation; the panel it opens floats,
so that keeps the scale's 4px. Noted in the component so it does not read as an
oversight.

**Verification**

104 tests still pass; `tsc`, `vite build` and `oxlint` clean. Driven in a
browser in both colour schemes: both panels open and close by click, Escape
(with focus returned) and outside click; the inverted button state marks the
open one; the panel keeps its contrast on the dark surface; and the enlarged
tiles, risk legend and empty states were all looked at rather than assumed.

**Follow-ups**

- The breakdown list is `max-w-sm`, so at the larger type the count sits a long
  way right of its label. Tolerable at one or two rows; worth tightening if the
  list regularly runs longer.
- `InfoButton` is the first disclosure of its kind here. `OrderDetailPage` and
  `BaselineActualChart` use bare `<details>` for a similar job; they could be
  unified if a third case appears.

### 2026-10-09 — Dashboard: section renames and a looser grid

**What changed**

The two section headings became one-word nouns — **"What came in" → "Incoming"**
and **"What we did" → "Actions"** — and the page was given room to breathe.

Spacing, roughly doubled where elements were crowding each other:

```
section padding        px-4 py-3   ->  px-6 py-6
page header            px-4 pb-2   ->  px-6 pb-4 pt-5
heading -> content     mt-3        ->  mt-5
between stat blocks    space-y-4   ->  space-y-6
between tiles          gap-x-10 gap-y-3  ->  gap-x-16 gap-y-6
risk legend            gap-x-6 gap-y-1   ->  gap-x-10 gap-y-2
breakdown rows         py-1        ->  py-2.5
```

**Decisions**

**Both headings were renamed, not one.** "What came in" and "What we did" were
written as a matched pair, so renaming only the second would have left an
asymmetry that reads as an oversight. "Incoming" and "Actions" are the same
part of speech at the same length, which is what keeps the two sections
legible as siblings.

**The breakdown list went `max-w-sm` -> `max-w-xs`.** The wider gutter left its
count stranded ~235px from its label at the new type size — a gap that reads as
two unrelated columns rather than one row. This was already logged as a
follow-up yesterday; the extra spacing made it worth doing now.

**Verification**

104 tests pass; `tsc`, `vite build` and `oxlint` clean. Looked at in a browser
at 1280px and at 420px: the headings read "Incoming" and "Actions", and the
wider gaps **do not** force a horizontal scrollbar at phone width — the tiles,
the risk legend and the period control all wrap, with `scrollWidth` asserted
equal to `clientWidth`.

**Follow-ups**

- The app shell's sidebar is a fixed 208px and does not collapse, so at 420px it
  takes half the viewport. Pre-existing and not introduced here, but the narrow
  check made it plain.

### 2026-10-09 — `clean_data.py` moved to the repo root and into git

**What changed**

`data/clean_data.py` — the Phase 0 cleaning script, and the one piece of
pipeline source that existed nowhere but this machine — moved to `clean_data.py`
at the repo root and is now tracked. `.gitignore` is untouched.

**Files touched**

```
data/clean_data.py -> clean_data.py    moved; docstring Run: block updated
docs/PROJECT_LOG.md                    §3 path corrected; §9 item resolved
```

**Decisions**

**Moved rather than excepted from `.gitignore`.** The alternative was
`data/*` plus `!data/clean_data.py`. It works — but only because of the `*`:
git cannot re-include a file whose parent *directory* is excluded, so the
otherwise-identical `data/` plus a negation silently ignores the file anyway.
Both forms were tested in a throwaway repo before choosing:

| `.gitignore` | `clean_data.py` | `big.p` | `clean/x.p` |
|---|---|---|---|
| `data/` + `!data/clean_data.py` | **ignored** | ignored | ignored |
| `data/*` + `!data/clean_data.py` | tracked | ignored | ignored |

That is a rule whose correctness rests on a character, protecting a file whose
absence from git is invisible until the disk fails. Moving the file removes the
rule instead of sharpening it: `data/` stays a plain wholesale exclusion, which
is what it should be for a ~1.5 GB directory of pickles.

**The root, not a new `pipeline/` directory.** The seven other pipeline scripts
(`profile_data.py`, `build_features.py`, `eval_harness.py`, `train_baselines.py`,
`sample_subgraph.py`, `build_graph.py`, `train_gnn.py`) are already at the root.
`clean_data.py` was not following a different convention down in `data/` — it was
the one Phase 0 script that never came up with its siblings. A `pipeline/` folder
would have fixed the ignore problem by splitting the pipeline across two
directories, trading one inconsistency for another.

**Nothing imported it, so nothing broke.** Grepped first: no `import clean_data`
anywhere, in any form. It is a standalone CLI script, and its only mentions are
prose — a `build_features.py` docstring and four documents, all naming it by bare
filename rather than by path, except the two `PROJECT_LOG.md` lines corrected here.

**The `"."` defaults were left alone and the docstring updated instead.** The
script resolves `raw_dir`/`out_dir` against the *working directory*, not against
`__file__`, so it was run as `cd data && python clean_data.py`; from the root that
becomes `python clean_data.py data data/clean`. Retargeting the defaults to
`data`/`data/clean` was tempting and rejected: `profile_data.py` (`data_dir: "."`)
and `build_features.py` (`clean_dir: "."`, `out_dir: "./features"`) both default to
`"."` and take the same two positional overrides. Consistency across the seven is
worth more than one script being convenient to run bare, so the `Run:` block now
states the root invocation and says the bare defaults are CWD-relative.

**Verification**

`git check-ignore -v data/clean_data.py` reported `.gitignore:8:data/` before the
move. After it: `git status` shows `clean_data.py` tracked, `git check-ignore`
still ignores `data/` and everything under it, and `git ls-files data/` is empty.
`python -m py_compile` passes and the edited docstring still parses as the module
docstring. The file had never been tracked on any branch — `git log --all --
'*clean_data.py'` was empty — so this is its first commit, not a restore.

**Follow-ups**

- **The script is committed but not reproducible.** Like the rest of the ML
  pipeline it needs pandas, and `backend/requirements.txt` covers the backend
  only — the `requirements-ml.txt` already noted as a follow-up on 2026-10-01
  would now cover this file too.
- **Its raw inputs remain untracked and unobtainable from this repo**, correctly:
  the six ~1.5 GB pickles are ignored and nothing records where they came from
  beyond "ASOS UK". The source file surviving is the point; the data was never
  going to.
- The archived checkpoints under `archive/checkpoints/` still describe
  `clean_data.py` in its Phase 0 context. They name it by bare filename, so none
  of them is now wrong, and they are historical records that are not rewritten.

### 2026-10-09 — Prepared for publication: audit, exclusions, a README, and a split repo

**What changed**

The repository was audited for material that should not be published, the
flagged material was untracked or redacted, and a separate publication copy
was built with a single commit. This repository is now the **private
archive**; the published copy is a sibling directory.

**Files touched**

```
docs/review/ (3 files)            NEW - the audit, the history residue and the
                                  credential scan. Retained in this archive
                                  only; not part of the published copy.
README.md                         NEW - the front page, and the deployment warning
.gitignore                        /Context/, /archive/india/, settings.local.json
Context/ (5), archive/india/ (4)  untracked via git rm -r --cached; still on disk
profile_data.py                   logs the data_dir as given, not abspath()
data_profile_report.md            regenerated, not hand-edited
archive/diagnostics/checks.py     relative data path
archive/README.md                 india + diagnostics sections corrected
backend/app/routers/meta.py       seed read degrades instead of 500ing
backend/tests/test_api.py         +1 test (105 total)
```

**Decisions**

**Excluded rather than redacted, for the PRD.** `Context/` holds a
condensation of an internal commercial PRD; `archive/india/` is built on its
assumptions and cites them in source. Both are untracked and gitignored,
still on disk. The audit's reasoning is recorded in the review documents
retained here.

**The review documents are not published.** They record an internal decision,
and between them they describe the PRD's contents, state that a private
archive still holds it, and collect the demo credentials in one place. Small
downside, no upside for a reader. They stay here.

**Two review documents reproduced the material they were describing.** The
first draft of the audit quoted the four PRD commercial figures as evidence
that the PRD is confidential, and quoted the machine's absolute paths while
recommending their removal. Both were caught by checking the *exported* tree
by content rather than by path, which is the check worth keeping: excluding a
path does not exclude the content if another file quotes it.

**A squash, not a history rewrite.** The PRD is reachable in 18 of the
pre-audit commits, so publishing this history would have published it.
Rather than `filter-repo`, the publication copy is a fresh `git init` over
`git archive HEAD` — it cannot inherit what it never had, and anyone holding
a clone of a filtered repo keeps the old objects anyway. This repository
keeps all 27 commits, which is what makes the residue record checkable and
keeps the `afb806a` recovery path alive.

**`git log --all -- <path>` understates residue twice over**, and both cases
were real: it lists commits that *touched* a path rather than those that
contain it (the `Context/` files were added once and never edited — 2 commits
listed, 18 containing), and it does not follow renames (the India files were
`git mv`'d from the repo root, hiding four earlier commits). Measured with
`git cat-file -e` per commit and `git log -S` instead.

**No real secret exists in any commit.** 22 commits scanned against 18 hard
credential patterns: zero. The only live credentials are the deliberate demo
admin and the fixed JWT fallback. gitleaks was *not* installed to do this —
it is not on this machine and was not installed silently; the scan is manual
and says so, with the install command and the expected output recorded so a
real run can be reconciled against it.

**The README leads with the warning, not the features.** The public admin
password and the forgeable JWT fallback were documented only in code comments
and §9 of this log. A reader lands on the warning first now, with the JWT
fallback called out as the sharper of the two: a known signing key bypasses
the login entirely, so changing the password does not help.

**Verification**

105 tests pass. The bug below was found by running the suite inside the
exported copy — the archive passes only because it has the gitignored seed
file on disk, which no clone does.

**Follow-ups**

- **The ASOS dataset's provenance and terms are still unrecorded.** The README
  now says so and tells a reader to establish them before using the data, but
  that is a disclaimer, not an answer.
- The published copy has no remote and nothing has been pushed from either
  repository.

### 2026-10-09 — Fix: `/api/meta` 500'd on any checkout without the seed JSON

**What changed**

`get_meta` opened `serving/output/orders_seed.json` unguarded. The file is
~29 MB and gitignored, so no clone has it until the export is run — which
retrains the model. Every fresh checkout therefore got a 500 on the endpoint
that feeds the prototype banner, and two smoke tests failed there.

**Decisions**

**Found by running the suite against a clean export, not here.** This working
copy has the seed file on disk, so the suite passed and had always passed.
The failure appeared the first time the tests ran inside the publication
copy. A test suite that depends on a gitignored artefact is green for the
wrong reason.

**The notice has to survive the provenance being unknown.** The banner exists
to say the data is illustrative. The seed read now degrades to the canonical
notice with `generated_at`/`model` stating the file is absent, and
`n_orders` still answered from the database — a degraded banner, not a
missing one.

**`PROTOTYPE_NOTICE` is imported from `serving.config`, not restated.** A
second copy of the disclaimer is exactly what the single-source arrangement
exists to prevent, and it would be the copy that goes stale.

**Pinned, and the pin was checked.** The new test monkeypatches the path to a
nonexistent file; it was confirmed to fail against the unguarded version
before being kept. Same lesson as the alerts 500 on 2026-10-01 — there the
endpoint had never been called at all, here it had never been called in the
state every clone is in.

**Follow-ups**

- Other endpoints read gitignored artefacts too. `/api/meta` is the one a
  clean checkout hits immediately, via the banner on every page; the rest
  were not audited for this.

### 2026-10-09 — A recorded baseline, and pinned dependencies for both halves

**What changed**

`docs/review/baseline.md` records what a green run looks like, and the two
requirements files now pin exact versions. The ML pipeline had no dependency
declaration at all before this — a gap noted as a follow-up on 2026-10-01.

**Files touched**

```
docs/review/baseline.md     NEW - test counts, known warnings, tool versions
requirements-ml.txt         NEW - 9 packages for the root scripts and serving/
backend/requirements.txt    8 packages, now pinned rather than floating
```

**Decisions**

**Both files were built from the imports, not from memory.** Every module
actually imported by the eight root phase scripts and `serving/` was extracted
with an AST walk, filtered against the standard library and this project's own
modules, and resolved to its installed version. That is where the ML list's
nine entries come from. It also confirmed what is *not* needed:
`torch-scatter` and `torch-sparse` are optional extensions of
`torch-geometric` and nothing here imports them.

**`backend/requirements.txt` was asymmetric and is no longer.** Only `pyjwt`
and `bcrypt` carried bounds, added in the auth change because a major bump in
an auth library is a behaviour change; the other six floated. "105 tests pass"
was therefore a claim about this machine rather than about a reconstructable
stack.

**The backend still needs none of the ML stack, and that was verified rather
than assumed.** `backend/app/routers/meta.py` imports `serving.config`, which
is the only backend-to-serving edge and could have dragged pandas into the API
— `serving/config.py` turns out to be pure constants with no imports at all.
The two files overlap only on pytest.

**Verification: a venv built empty, then the same thing inside a clean export.**
Not the project `.venv` with packages removed — a new 3.12.14 environment
containing only pip, installed from the two files, with no access to this
machine's site-packages. 105 tests pass there, and 105 pass again in a
`git archive` export holding none of the gitignored artefacts. That second
run is the one that matters: it is what a fresh clone actually gets.

**Pinning direct dependencies does not pin the environment**, and the proof
showed up immediately. The suite reports 3 warnings here and 2 in the fresh
venv, because this `.venv` has starlette 1.6.0 while a clean install resolves
1.7.0, where the `anyio.abc.BlockingPortal` deprecation is fixed. Starlette is
not pinned and should not be under the rule these files follow — nothing
imports it; it arrives underneath FastAPI. The baseline therefore records the
**test count as fixed and the warning count as environment-dependent**, which
is the honest distinction. A full `pip freeze` lockfile beside these files is
the answer if exact reproducibility ever outweighs readability.

**The third pytest warning is not noise worth muting.** `InsecureKeyLengthWarning:
The HMAC key is 13 bytes long` is the test suite signing with the fixed
development key — the same key `publish-audit.md` B4 describes as forgeable.
It is pointing at a real property of the default configuration, and it goes
away when `RETURNS_DASHBOARD_JWT_SECRET` is set, which any deployment must do.

**Verification**

105 tests, `npm run build` clean, `npm run lint` 0 errors / 2 warnings — the
two long-standing `only-export-components` hints. Matches the baseline, which
is now the thing later changes are measured against.

**Follow-ups**

- **`requirements-ml.txt` is declared but not exercised by CI or by the test
  suite.** `serving/tests` needs only pandas and pytest; nothing in the suite
  imports torch, so a broken pin on the graph stack would not fail anything.
  The pins were verified by installing them, not by running the pipeline.
- The pinned versions are current as of today and will age. Nothing refreshes
  them, and a stale pin fails loudly at install rather than quietly at runtime,
  which is the right failure mode but still a maintenance task.

### 2026-10-11 — Plain-language rewrite of the docs and every code comment

**What changed.** The goal was a repository that someone with no background
in this project can read on GitHub. Only prose changed — no code, and no text
the app or scripts show on screen.

- `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md` and `frontend/README.md`
  were rewritten in plain words: short sentences, jargon explained or replaced
  ("cold-start" → "new customer", "tenant" → "company", "seed JSON" → "the
  dashboard's data file"), the reasoning kept, the build history dropped.
- `docs/checkpoint_phase0_phase3.md` gained an "In plain words" summary at the
  top. The technical body is unchanged.
- This log: only the intro was rewritten. Old entries are untouched, per the
  project's rule.
- Every comment and docstring in the Python (44 files), TypeScript and TSX
  (all of `frontend/src`), CSS, `index.html`, `vite.config.ts`, `run_dev.sh`,
  `.gitignore`, `.env.example` and both requirements files. References to the
  internal PRD, which is not published, were taken out of comments.

**Factual fixes made along the way.** README no longer lists a folder of
private review notes that isn't published. ARCHITECTURE now says `serving/export_seed.py` reads
`train_gnn.CONFIG`. CONTRIBUTING describes the alignment check by its code
(`assert len(display_df) == len(test_prob)`) rather than a line number. A
stale `target_events=40000` comment in `export_seed.py` now says 20000.
`run_dev.sh --help`, which prints lines 2–11 of the script, used to stop
mid-sentence; the header now fits those lines, with a note saying so.

**How "comments only" was proven, file by file.** Python: the syntax tree of
each file, with docstrings removed, compared against `HEAD`. TypeScript: the
whole app compiled with `tsc --removeComments` at `HEAD` and now, and the 55
output files compared. CSS and HTML: compared with comments stripped. Shell
and config files: compared with `#` lines removed. Each checker was first
shown to catch a deliberate one-character code change. All report no code
changes.

**Decisions.**
- Text the user sees was left alone even where it's technical — log messages
  such as `profile_data.py`'s "(PRD)" line, `run_dev.sh`'s status messages,
  and every label in the app. Changing those changes behaviour and tests.
- Constant and function names stay in comments where a developer needs them.

**Verification.** 103 tests pass; `npm run build` clean; `npm run lint`
0 errors and the 2 known warnings.

**Follow-ups.**
- This log has no entries for the work between the 2026-10-09 baseline and
  this one: the four layer clean-ups, removing `GET /api/roles`, the new
  README/ARCHITECTURE/CONTRIBUTING, and the move to the new public repository.
  The commits record it; the log does not.
- User-facing messages could get the same plain-language pass if wanted.
