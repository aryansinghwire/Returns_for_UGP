# The website

This folder is the dashboard's website, built with React, TypeScript, Vite and
Tailwind. It talks to the server in `backend/`.

The easiest way to run it is from the main project folder with `./run_dev.sh`,
which starts the website and the server together. If you start the website on
its own, it will load but show no data, because there's no server for it to
talk to.

```bash
npm run dev     # the website only — the server must already be running on port 8000
npm run build   # check the code and build the website
npm run lint    # check the code style
```

Open **http://localhost:5173**. Use `localhost` — the address `127.0.0.1`
won't load here.

What's where:

- `src/api/` — talks to the server, and describes the shape of the data it
  sends back (matching `backend/app/schemas.py`)
- `src/pages/` — one file per page
- `src/components/` — the pieces pages are built from
- `src/lib/` — small helpers: number and date formatting, saving filters in the
  web address, and the risk colours (the only place colour is allowed to mean
  something)
- `src/context/` — who's logged in, and which company they're looking at

There are no automated tests for the website. `npm run build` and
`npm run lint` check that the code is valid, but not that the pages work.

See [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for where to start on a change,
and [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for the mistakes to avoid.
