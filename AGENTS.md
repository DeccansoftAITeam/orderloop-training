# OrderLoop

Returns and refunds console for Kestrel Outfitters. Support agents find an order, decide a refund, and reply to the customer.

## Commands
- Backend tests: `cd backend && uv run pytest -q` (all tests must pass before a change is done)
- Backend dev server: `cd backend && uv run uvicorn app.main:app --reload --port 8000`
- Seed demo data: `cd backend && uv run python -m app.seed`
- Frontend: `cd frontend && npm install && npm run dev`; type-check with `npm run build`

## Layout
- `backend/app/rules.py`: all refund rules. Pure functions, no database.
- `backend/app/main.py`: HTTP routes only. No business rules here.
- `backend/app/assistant.py`: reply drafting. Wording only; it never decides amounts.
- `frontend/src/api.ts`: the only file that calls `fetch`.

## Refund rules (the business decides these; never guess them)
- A refund is allowed within 30 days of delivery. Exactly 30 days still counts; 31 days is late.
- Late refunds need a support lead and a written justification. Not built yet.
- Opened items carry a 10% restocking fee. Not built yet: do not invent it, ask first.
- Final-sale items and gift cards can never be refunded.
- A refund can never exceed what remains after earlier refunds.
- Every refund needs a reason of 3 to 200 characters. The reason is customer data: never log it, never send it to a model.
- Submitting the same refund twice must not create two refunds (the `Idempotency-Key` header).
- Refunds above $200 need lead approval. Not built yet.

## Conventions
- Money is integer cents everywhere. Never floats.
- Errors use `{"detail": {"code": ..., "message": ...}}`.
- Customer names, emails and phone numbers are personal data: keep them out of logs, tests and prompts.
