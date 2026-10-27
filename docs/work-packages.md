# Work packages: parallel build

Three independent packages. Each one owns its files; no file appears twice, except `CHANGELOG.md`, which is shared on purpose (see "The shared line"). Each package is built on its own branch in its own worktree and merged by the lead.

The lane guard (`.claude/hooks/lane_guard.py`, rules in `.claude/lanes.json`) denies edits to any file a lane does not own.

| Lane | Branch name | Package | Owns |
|---|---|---|---|
| A | `wp-a` | Backend: refund statistics endpoint | `backend/app/stats.py`, `backend/app/main.py`, `backend/tests/test_stats.py`, `CHANGELOG.md` |
| B | `wp-b` | Frontend: order status filter | `frontend/src/App.tsx`, `frontend/src/api.ts`, `CHANGELOG.md` |
| C | `wp-c` | Docs: API reference | `docs/api.md` |

## WP-A: refund statistics endpoint

Add `GET /stats/refunds`. On the seeded test data (which already holds one refund of 5000 cents) it answers `200` with exactly this JSON:

```json
{ "refund_count": 1, "refunded_cents": 5000 }
```

- `refund_count` is the number of rows in the `refunds` table; `refunded_cents` is the sum of `amount_cents` (0 when there are none).
- Money is integer cents.
- The query lives in a function `refund_stats(conn)` in `backend/app/stats.py`; `main.py` only adds the route.
- Tests first, in `backend/tests/test_stats.py`: one on the seeded data, one after two more refunds are posted through the API.
- Done when: `cd backend && uv run pytest -q` passes.

## WP-B: order status filter

The API already accepts `GET /orders?status=<value>`. Add a drop-down above the order table that filters by status.

- `listOrders(q, status?)` in `frontend/src/api.ts` sends `status` only when it is not empty.
- A `<select>` in `frontend/src/App.tsx` with the options: All (empty value), `delivered`, `shipped`.
- No backend change.
- Done when: `cd frontend && npm install && npm run build` passes.

## WP-C: API reference

Create `docs/api.md` describing the endpoints that exist today (`/health`, `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/refunds`, `POST /orders/{id}/reply-draft`): method, path, parameters, and the error codes the refund endpoint returns. Read `backend/app/main.py` and `backend/app/rules.py` for the facts.

- One H2 heading per endpoint.
- Do not document `/stats/refunds` (it does not exist on your branch yet).
- Done when: the file exists and names every endpoint above.

## The shared line

`CHANGELOG.md` has one placeholder line under `## Unreleased`. WP-A and WP-B each replace that same line with one bullet about their change. WP-C does not touch the changelog. When the second of A and B is merged, Git reports a conflict on that line. The lead resolves it by keeping **both** bullets and removing the placeholder.
