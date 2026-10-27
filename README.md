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

## Reply drafting: template or Claude

Each seeded order comes with a synthetic inbound customer message (`backend/app/messages.py`). The reply panel loads it as a default, so you can press **Draft reply** straight away or edit the text first. Some messages contain a fake email or phone number so you can see the masking work.


The reply draft comes from one of two providers, chosen by `ORDERLOOP_DRAFT_PROVIDER`:

| Value | What it does |
|---|---|
| `template` (default) | Deterministic, offline wording that varies by situation. No key, no network. |
| `claude` | Calls the Anthropic API through the official `anthropic` SDK. |

To use Claude, set the key in the shell that starts the backend. The key is read only from the standard `ANTHROPIC_API_KEY` variable. Never commit it. For local convenience you may keep it in an untracked `.env` (already in `.gitignore`) and start the backend with `uv run --env-file ../.env uvicorn app.main:app --reload --port 8000`.

A user-level key that is not tied to one workspace also needs `ANTHROPIC_WORKSPACE_ID` (the workspace id from the Anthropic console); it is sent as the `anthropic-workspace-id` header. A workspace-scoped key does not need it.

PowerShell:

```
$env:ORDERLOOP_DRAFT_PROVIDER = "claude"
$env:ANTHROPIC_API_KEY = Read-Host "Anthropic API key"   # or paste it; it stays in this session only
uv run uvicorn app.main:app --reload --port 8000
```

bash:

```
export ORDERLOOP_DRAFT_PROVIDER=claude
read -rs ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY
uv run uvicorn app.main:app --reload --port 8000
```

The default model is `claude-haiku-5-5` (cheap); set `ORDERLOOP_DRAFT_MODEL` to use another. `GET /assistant/status` returns `{"provider", "model", "configured"}` (never the key). If `claude` is selected and no key is set, the draft endpoint returns `503` with `{"detail": {"code": "draft_provider_unavailable", ...}}`.

Privacy: the model sees only the masked customer message, item names, delivery timing, the refund decision from `rules.py` and a tone instruction. It never sees the customer's name, email, phone, address or the refund reason. It writes `{first_name}` and the backend fills in the real first name afterwards. A draft containing a dollar amount that `rules.py` did not produce is regenerated once, then replaced by the template draft with `"fallback": "claude_draft_rejected"`. Prompts and drafts are not logged. The response adds `provider` and `model` to the existing fields.

## Run the tests

```
cd backend
uv run pytest -q
```

Expected: `40 passed` on `main`. The lab start tags have fewer (for example `37 passed` at `lab-01-start`).

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
