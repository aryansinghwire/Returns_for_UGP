# How the code is organised

This page explains where things live, how a prediction travels from the model
to the dashboard, and why the project is built the way it is.

For the story of how it was built, see
[`docs/history/PROJECT_LOG.md`](docs/history/PROJECT_LOG.md).

## Where to start for a change

| To change… | Start in | Also check |
|---|---|---|
| how the model works | `train_gnn.py` (`GNNEncoder`, `EdgeDecoder`, `Model`) | `serving/export_seed.py` uses the same classes |
| a model setting (like the number of training rounds) | `train_gnn.CONFIG` | nothing else — `serving/export_seed.py` reads the settings from here |
| the size of the data sample | `sample_subgraph.py` — `n_seed_products`, plus the number you pass on the command line | `export_seed.py` warns you if the number of test orders is no longer 16,246 |
| what the model learns from | `build_features.py` | `build_graph.py`, `export_seed.py`, `serving/reasons.py`, then the backend |
| the explanations shown for each order | `serving/reasons.py` | the thresholds in `serving/config.py`; re-run with `export_seed.py --reasons-only` to skip retraining |
| which details are made up | `serving/config.py` | this is the only place — order numbers, dates and company names all come from here |
| the database tables | `backend/app/models.py` | there's no upgrade system: new tables appear automatically, new columns don't |
| a web address the server answers | `backend/app/routers/` | keep these short — put the real work in `services/` |
| who can see or do what | `backend/app/deps.py` | the core of the security; also `config.ROLE_LEVELS` and `constants.ROLES` |
| the list of actions staff can take | `backend/app/constants.py` | and `frontend/src/api/types.ts` — both must change together |
| when an alert fires | `backend/app/config.py` | all four settings are there |
| where "low / medium / high risk" begins | `frontend/src/lib/risk.ts` | and `backend/app/services/dashboard.py` — two files, two languages, must match |
| the order list or its filters | `frontend/src/pages/QueuePage.tsx`, `components/FilterPanel.tsx` | `routers/orders.py` uses one shared filter for the list and the chart above it |
| colours, fonts, spacing | `frontend/src/index.css`, `lib/controls.ts` | `lib/risk.ts` is the only place colour is allowed to mean something |

## How a prediction reaches the dashboard

```
six raw data files   (ASOS UK — not in this repository)
  │  clean_data.py        fix known problems in the raw files
  ▼
data/clean/
  │  build_features.py    turn each order into numbers the model can use
  ▼
data/features/
  │  sample_subgraph.py   take a connected sample of customers and products:
  │                         400 products · 35,348 customers · 36,114 orders
  │                         19,868 for training (Sep–Oct) · 16,246 for testing (Oct–Nov)
  │  build_graph.py       link each customer to the products they bought
  ▼
data/graph/
  │  train_gnn.py         train the model on the training orders only
  │                       (showing it the test orders would be cheating)
  ▼
  │  serving/export_seed.py
  │    trains the same model again and scores the 16,246 test orders.
  │    It matches each score to its order by position in the list, so it
  │    first checks that the two lists are the same length.
  │    synth.py adds the made-up order numbers, dates and companies;
  │    reasons.py adds a short explanation for each score.
  ▼
serving/output/orders_seed.json   (about 29 MB — not in this repository)
  │  backend/scripts/seed_db.py   loads it into the database
  ▼
Database (SQLite)
  orders            never changes — exactly what the model saw and scored
  order_status      changes — where each order stands right now
  intervention_log  only ever added to — what people did, and when
  plus tenants, users, automated_rules, baseline_stats
  │  The server (FastAPI) reads from here
  ▼
The website (React)
```

The model's original score is never changed after loading. If someone
overrides a score, the new one goes in `order_status` and the change is written
to `intervention_log` — so the model's original answer can always be checked.

### How alerts work

Alerts don't use the model at all. They watch for groups of orders being
returned more often than usual.

When the database is loaded, `seed_db.py` works out each group's normal return
rate and stores it in `baseline_stats`. A "group" is all orders for one product,
one country, or one product type.

Then, for each group, `services/alerts.py` compares:

```
recent rate  = how often recent orders in the group were returned
normal rate  = that group's usual rate, from baseline_stats
gap          = recent rate − normal rate

raise an alert when  gap ≥ 0.15  and the group has at least 15 recent orders
call it "high"       when gap ≥ 0.25, otherwise "medium"
```

"Recent" means the last 14 days. All four numbers live in
`backend/app/config.py`, as `ALERT_MIN_GAP`, `ALERT_MIN_N`, `ALERT_HIGH_GAP` and
`ALERT_WINDOW_DAYS`. Alerts aren't stored — they're worked out fresh each
time someone loads the page.

The 15-order minimum matters: the test data has only about 397 different
products, and without it, small groups would trigger alerts constantly just by
chance.

"The last 14 days" is counted back from the **newest order in the data**, not
from today. The order dates are made up and end in 2021, so counting from today
would never find anything. `services/dates.py` holds this rule so the order
list's date filter and the alerts always agree.

This is the only place the real return outcomes are read, and only as group
totals — never for a single order.

## Design decisions

Each one says what was decided and why.

### The model

**Use the simplest model that works.** The basic GraphSAGE model beat every
more complex version, so it's the one used. The complex versions were still
built and tested, so the project can show *that* they didn't help, not just
claim it.

**Work on a small, connected sample.** At full size, the data breaks into many
separate pieces that don't link to each other. A connected sample is the only
way to properly test a model that learns from links between customers and
products. The trade-off is explained in the write-up's limitations section.

**Use the test orders as the dashboard's orders.** The model can only score the
16,246 test orders in its sample, so those are the orders the dashboard shows.
It can't yet score a new order.

### Being honest about made-up data

**Anything invented is clearly labelled as invented, everywhere.** The original
data has no order numbers, dates or company names, and the dashboard needs all
three. So they're invented — order numbers always start with `DEMO-ORD-`, every
response from the server is tagged `X-Prototype: true`, and a banner on every
page says so. That banner's wording is written once, in
`serving/config.PROTOTYPE_NOTICE`, so it can't drift.

**The real outcome is never shown for a single order.** The data records whether
each order was actually returned. Showing that next to an order would give away
the answer, so it only appears as group totals in alerts and reports, labelled
as past results.

**Explanations only mention real, named details.** They never use the 13
lettered return-reason codes, because nobody knows what those mean. They also
never mention age, year of birth, gender or premium membership. The first three
are protected characteristics, and the effect of the last was never measured.
The model still uses all four; the explanations shown to staff don't.

### The server

**Use a real database, not a file.** Saving overrides and actions needs safe,
reliable updates and fast searching across 16,000 orders. A plain file would
have to be rewritten in full every time anything changed.

**Keep three separate tables for three different jobs.** One records what the
model saw, one records where each order stands now, and one records what people
did. Merging them would lose the history.

**There's no upgrade system for the database.** The server can add a missing
table by itself, but it can't add a missing column to an existing table. It
repairs exactly one known old layout on startup — by deleting and recreating
the automatic-rules table, which is safe only because rules are quick to
re-enter. That approach must never be used on the users table, which holds the
only copy of everyone's account.

**Each company's data is kept separate by the server, not by the website.**
Everyone except the platform admin only ever sees their own company's data. If
someone asks for another company's data, the server refuses with an error
rather than quietly showing them their own — so they know the request didn't
work.

**The server checks each user's role in the database every time.** It doesn't
trust the role stored in their login token. If it did, someone who'd been
demoted or disabled would keep their old access until their login expired —
up to eight hours later.

**Rules work on a range of scores, not just a minimum.** That lets a company
send medium-risk orders to a cheap action (like an email) and high-risk orders
to an expensive one (like a phone call), without the two overlapping.

**Rules only run when someone presses the button.** A scheduling system would
be overkill for a demo.

### The website

**Bulk actions ask first, and show what they'll do.** Running the rules can
affect thousands of orders at once. Before it does, a confirmation box shows
how many orders each rule will touch, and the confirm button stays disabled
until those numbers have loaded. It also says plainly that there's no undo.

**An undo feature was built, then removed on purpose.** It worked, but it
complicated a history table that's meant to only ever be added to. Making the
warning clear was simpler than making the action reversible.

**"Approved for delivery" counts as an action.** Deciding an order is fine is a
real decision, and it's worth recording.

**Colour only means risk.** Everything else on screen is black, white and grey.
The only colours are green, yellow and red for risk, and they use the same
cut-off points as the words "low", "medium" and "high" — so the colour and the
word can never disagree. Colour is never the only clue: the score and the word
always appear next to it, for people who can't tell the colours apart.

**The reporting page is switched off, not deleted.** Its link is gone and its
address redirects elsewhere. The page's code is still here, but nothing uses it
any more. Whether to bring it back or remove it is still undecided — see
section 9 of the project log.

### Keeping the project tidy

**Old work is put aside, not deleted.** Experiments that didn't make it in,
earlier write-ups and one-off scripts are moved aside with a note, so any result
can still be checked against the code that produced it. That archive is kept
privately and isn't part of this repository; what it found is in
`docs/checkpoint_phase0_phase3.md`.

**`run_dev.sh` exists because starting the project by hand was easy to get
wrong.** The commands need the right Python, the server has to be started from
the main folder, and the website has to use `localhost` rather than
`127.0.0.1`. Worse, an old copy of the server could keep running in the
background while the new one silently failed to start — so the page loaded old
code with no error anywhere. The script clears out old copies first and checks
the server is really running.
