# OrderLoop

A returns and refunds console for a small online store (Kestrel Outfitters). Support agents search orders, check refund eligibility, record a refund, and draft a reply to the customer.

This is the sample app for the course **The Agentic Engineer: Mastering Claude Code for the SDLC**. All customer data is synthetic.

## What is in the repo

| Folder | What it is |
|---|---|
| `backend/` | FastAPI + SQLite API. Refund rules are in `backend/app/rules.py` |
| `frontend/` | React + Vite + TypeScript screen: order queue, order detail, refund form, reply draft |
| `seed/` | Synthetic customer data (`customers.csv`) |

## Run it

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/) and Node.js 22+.

Backend (terminal 1):

```
cd backend
uv sync
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

Frontend (terminal 2):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Run the tests

```
cd backend
uv run pytest -q
```

Expected: `20 passed` on `main`. The lab start tags have fewer (for example `17 passed` at `lab-01-start`).

## How the labs use this repo

Fork this repository once (see `Lab-00-Fork-and-Setup` in the course handouts), clone your fork, add this repository as `upstream` and fetch its tags:

```
git remote add upstream https://github.com/DeccansoftAITeam/orderloop-training.git
git fetch upstream --tags
```

Every lab starts from a tag. Create your own branch from it and never commit to `main`:

```
git switch -c lab-02 lab-02-start
```

Labs do not depend on each other. If you get stuck, compare with the branch `lab-NN-solution` without merging it:

```
git fetch upstream
git diff lab-02 upstream/lab-02-solution
```
