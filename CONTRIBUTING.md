# Working on this project

## Setting up

You need **Python 3.12** and **Node.js**. Type `python3.12` exactly — on many
computers, plain `python3` is a newer version that these packages weren't
tested on.

There are two sets of Python packages. The server only needs the first:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt   # the server and its tests
.venv/bin/python -m pip install -r requirements-ml.txt        # the machine-learning tools
cd frontend && npm install
```

Both files list exact versions, so everyone ends up with the same setup.

With only the first set installed, you can run the server and 87 of the 103
tests. The other 16 tests need the machine-learning packages. If you try to run
them without, you'll see `ModuleNotFoundError: No module named 'pandas'`. That
just means the second set isn't installed — nothing is broken.

To change any settings, copy `.env.example` to `.env`. Git ignores `.env`, and
`run_dev.sh` reads it automatically.

## Running the tests

```bash
.venv/bin/python -m pytest backend/tests -q                 # 87 tests, server packages only
.venv/bin/python -m pytest backend/tests serving/tests -q   # 103 tests, needs both sets
cd frontend && npm run build                                # checks and builds the website
cd frontend && npm run lint                                 # checks the code style
```

**Everything is fine when you see 103 tests pass, the build succeed, and the
style check report 0 errors and 2 warnings.** The two warnings are old and
harmless — they're in `AppContext.tsx` and `AuthContext.tsx`. If a third one
appears, or the test count drops, something has changed.

The tests don't cover everything:

- **The website has no tests.** The build and style checks only prove the code
  is valid, not that the pages work.
- **The database loader and the machine-learning scripts aren't tested.** The
  tests create their own small set of fake orders. If you change the loader,
  run it against a throwaway database to check it:

```bash
RETURNS_DASHBOARD_DB_URL="sqlite:////tmp/check.db" \
  .venv/bin/python -m backend.scripts.seed_db
```

A correct run loads 16,246 orders, 3 companies and 1,239 group averages.

The tests also pass on a fresh copy of the code with none of the large data
files present. That's worth checking if you change anything that reads a file:

```bash
git archive --format=tar HEAD | (cd <empty-folder> && tar xf -)
```

## Things not to do

Each of these has caused a problem before.

**Don't rename `LEGACY_KEYS` or `LEGACY_DEMO_ADMIN_EMAIL`.** These hold the old
names of things an earlier version of the app saved, so the app can find and
clean them up. Rename them and the app can't find the old data any more — stale
settings stay in people's browsers forever, or a second admin account appears
that nobody knows about.

**Don't rename saved values like `convert_cod_to_prepaid`.** Every action staff
take is saved under its name, in a history that's never edited. Rename one and
every old record of it points to an action that no longer exists. If you want
it to look different on screen, change its label instead — the saved name and
the label are kept separate for exactly this reason.

**Don't copy the `_drop_stale_rules_table` trick onto the users table.** That
function deletes and recreates a table when the app starts, to fix an old
layout. It's only acceptable for the automatic-rules table, because rules are
quick to type in again. The users table holds the only copy of everyone's
account — doing the same thing there would delete them.

**Don't remove the length check in `serving/export_seed.py`.** That script
matches each score to its order by their position in two lists, not by any ID.
The line `assert len(display_df) == len(test_prob)` is the only thing making
sure the two lists still line up. Without it, an order could quietly end up with
someone else's risk score.

**Don't use `127.0.0.1` for the website.** The page won't load. Use
`localhost`.

**Don't show the real outcome on a single order.** The data records whether
each order was actually returned. The dashboard is meant to work as if it
doesn't know that yet. The outcome may only appear as group totals, in alerts
and reports, labelled as past results.

**Don't give the 13 lettered return-reason codes a meaning.** Nobody knows what
they stand for. No explanation shown to staff may be based on them — or on age,
year of birth, gender or premium membership. The first three are protected
characteristics, and the effect of the last was never measured.

## How to write code here

- Do the simplest thing that works. Delete code before adding new layers.
- Build for the problem you have, not ones you might have later.
- Keep each fact in one place. Two copies of the same list or number will drift
  apart.
- Use names from the business — order, company, escalation, new customer — not
  vague ones like helper, manager, data or utils.
- Keep each function and component to one job, short enough to read on one
  screen.
- Use comments to explain *why* something is done, not *what* the code does.
- Start every file with a short note saying what it's for and what it mustn't
  do.

Keep all three checks passing with every change, and make one kind of change
per commit.

## Adding things

### A new action staff can take

Change two files together. Python and TypeScript can't check each other, so
nothing will warn you if you only change one:

1. `backend/app/constants.py` — add it to `ACTION_TYPES`. Automatic rules will
   be able to use it too, unless it hands the order to another person like
   `escalate` does. Hand-offs are left out of rules on purpose: a rule could
   pass thousands of orders to one admin in a single click.
2. `frontend/src/api/types.ts` — add it to `ACTION_TYPES` and give it a label
   in `ACTION_LABELS`. If you forget the label, the website won't build, so
   you'll find out straight away.

Choose the name carefully. It's saved permanently, so it can never be renamed.
You don't need to change the database or add anything else.

### A new role

Roles are listed in five places, and this is the change most likely to go
wrong:

1. `backend/app/config.py`, `ROLE_LEVELS` — how much the role is allowed to do.
2. `backend/app/constants.py`, `ROLES` — the name shown in the account menu.
3. `backend/app/config.py`, `SIGNUP_ROLES` — only if people may choose it when
   signing up. `admin` is deliberately left out.
4. `backend/app/models.py`, the `ck_users_role_tenant` rule — only if the new
   role works differently with companies. Changing this means rebuilding the
   users table, which holds the only copy of everyone's account.
5. `frontend/src/api/types.ts` — the `Role` list, `ALL_ROLES`, `ROLE_LABELS`,
   and `ADMIN_AREA_ROLES` or `SIGNUP_ROLES` if it belongs in either.

That's all. The website's menu and its page guards both read
`ADMIN_AREA_ROLES`, so they can't disagree.

If you forget step 1, you'll know at once — the server refuses every request
from anyone with the new role. If you forget step 2, it's easy to miss: everything works, but the account
menu shows a blank where the role's name should be.

### A new page on the server

1. Add it to the right file in `backend/app/routers/`. Keep it short, and put
   the real work in `services/`.
2. Decide who can see it. Use `get_scoped_tenant_or_none` if the platform admin
   may see every company's data, or `require_tenant_scope` if one company must
   be named. Protect anything that changes data with `require_role(...)`.
3. **Leave the `role: str = Depends(require_role(...))` line in, even if the
   function never uses `role`.** That line *is* the permission check — it runs
   before the function does. Delete it because it looks unused and the page
   becomes open to everyone who's logged in.
4. Describe what it returns in `backend/app/schemas.py`, and copy that shape
   into `frontend/src/api/types.ts`. The two files match exactly today; keep it
   that way.
5. Add its address to `READ_ENDPOINTS_ANY_ROLE` or `READ_ENDPOINTS_TENANT_ADMIN`
   in `backend/tests/test_api.py`. That test simply checks every page loads,
   and it exists because a page once broke without any test noticing. Adding an
   address there adds **two** tests — one for each role — so the expected count
   goes up by two.
6. If its address starts with `/orders`, put it above the `/{order_id}` route,
   or the server will mistake the rest of the address for an order number.

## Further reading

- [`README.md`](README.md) — what this project is, and the demo warnings.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the code is organised, and why.
- [`docs/checkpoint_phase0_phase3.md`](docs/checkpoint_phase0_phase3.md) — the
  full machine-learning write-up.
- [`docs/history/PROJECT_LOG.md`](docs/history/PROJECT_LOG.md) — a diary of how
  the project was built, and a list of open issues in section 9. New work is
  added to the end of it, and old entries are never rewritten.
