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

Expected: `40 passed` on `main`. Lab start tags show 37 to 40, and each lab guide states its own number.

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

## What you build in each lab

Branches and tags in this repository:

| Name | What it is |
|---|---|
| `main` | The finished sample app (this README). Never commit to it. |
| `lab-NN-start` (tag) | The starting point of lab NN. You branch from it. |
| `lab-NN-solution` (branch) | One worked answer for lab NN, for catching up. Compare, do not merge. |
| `capstone-start`, `capstone-solution` | The same pair for the capstone. |
| `flawed-pr` | A deliberately flawed pull request that Lab 16 asks you to review. Not a lab start. |

Every lab starts from the same OrderLoop app and adds one piece of the agent system around it. Labs are independent: do any lab without the others.

| Lab | Start tag | You build |
|---|---|---|
| 1 First session and memory | `lab-01-start` | `AGENTS.md` and path rules that stop Claude guessing the refund rules |
| 2 Plan, implement, verify | `lab-02-start` | The 10% restocking fee, planned in plan mode and written tests-first; you also rewind a wrong turn |
| 3 Skills: build one | `lab-03-start` | A model-invoked `add-refund-rule` skill and a user-invoked `pr-summary` skill |
| 4 Skills: compose and test | `lab-04-start` | A skill with a script and a reference file, plus a forked review skill |
| 5 Subagents and orchestration | `lab-05-start` | Six role subagents, run as a pipeline, a parallel fan-out and a writer and reviewer loop, to add a refund-status filter |
| 6 Permissions | `lab-06-start` | Allow, ask and deny rules that protect the customer data file and block pushes to `main` |
| 7 Hooks | `lab-07-start` | Hooks that block reads of secrets, run tests after an edit, and write an audit log |
| 8 Connect MCP | `lab-08-start` | A project-scoped MCP server connection, inspected and permission-controlled |
| 9 Build an MCP server | `lab-09-start` | The `orderloop` MCP server: three read-only tools with masked contact details |
| 10 Refund Triage agent | `lab-10-start` | A skill, a limited subagent, a guard hook and permissions assembled into one agent |
| 11 Plugin | `lab-11-start` | The `orderloop-sdlc` plugin, installed from a local marketplace |
| 12 Spec-driven feature | `lab-12-start` | A spec for lead approval of large refunds, then one work package built tests-first |
| 13 Parallel work | `lab-13-start` | Three work packages in separate worktrees, merged with one conflict resolved |
| 14 Agent teams | `lab-14-start` | A small review team on one change, with a written debate (experimental) |
| 15 Legacy migration | `lab-15-start` | A Python 2 settlement job migrated to Python 3 behind golden-output tests |
| 16 Review and audit | `lab-16-start` | A `REVIEW.md` of findings by severity for the flawed pull request (`flawed-pr`) |
| 17 Headless and CI | `lab-17-start` | A fail-closed AI review gate and a GitHub Actions workflow |
| 18 Security | `lab-18-start` | Injection tests against the agent, the control that stops them, and secret scanning |
| 19 Evals | `lab-19-start` | A small eval harness with code-based graders and replayed runs |
| 20 Agent SDK | `lab-20-start` | A Python script that calls the Agent SDK with typed output and a dry-run mode |
| Capstone | `capstone-start` | One new feature end to end: spec, tests first, review and a pull request with a green CI run |
