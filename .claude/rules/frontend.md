---
paths:
  - "frontend/src/**/*.{ts,tsx}"
---

# Frontend rules

- Function components with hooks. TypeScript strict mode; no `any`.
- Only `src/api.ts` calls `fetch`.
- Amounts from the API are cents; show them in dollars.
