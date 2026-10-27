export interface OrderSummary {
  id: number;
  status: string;
  customer_name: string;
  total_cents: number;
  delivered_at: string | null;
}

export interface OrderItem {
  sku: string;
  name: string;
  qty: number;
  unit_price_cents?: number;
  total_cents: number;
  refundable: boolean;
  opened?: boolean;
  final_sale?: boolean;
  gift_card?: boolean;
}

export interface Refund {
  id: number;
  amount_cents: number;
  reason: string;
  created_at?: string;
}

export interface Eligibility {
  eligible: boolean;
  late: boolean;
  days_since_delivery: number | null;
  max_refundable_cents: number;
  blockers: string[];
  restocking_fee_cents?: number;
}

export interface OrderDetail {
  id: number;
  status: string;
  placed_at?: string | null;
  delivered_at?: string | null;
  customer: { id: number; name: string };
  items: OrderItem[];
  refunds: Refund[];
  eligibility: Eligibility;
}

export interface ReplyDraft {
  draft: string;
  provider?: "template" | "claude";
  model?: string;
}

export interface AssistantStatus {
  provider: "template" | "claude";
  model?: string;
  configured?: boolean;
}

export class ApiError extends Error {
  code: string | null;
  constructor(message: string, code: string | null) {
    super(message);
    this.code = code;
  }
}

interface ErrorBody {
  detail?: { code?: string; message?: string } | string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  const body: unknown = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as ErrorBody).detail;
    const message =
      typeof detail === "object" && detail?.message ? detail.message : `Request failed (${res.status})`;
    throw new ApiError(message, typeof detail === "object" ? (detail?.code ?? null) : null);
  }
  return body as T;
}

export const listOrders = (q: string) => request<OrderSummary[]>(`/orders?q=${encodeURIComponent(q)}`);
export const getOrder = (id: number) => request<OrderDetail>(`/orders/${id}`);

export const createRefund = (id: number, amountCents: number, reason: string, idempotencyKey: string) =>
  request<{ id: number; replayed?: boolean }>(`/orders/${id}/refunds`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ amount_cents: amountCents, reason }),
  });

export const draftReply = (id: number, message: string) =>
  request<ReplyDraft>(`/orders/${id}/reply-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

/** Returns null when the backend does not offer the endpoint yet. */
export const getAssistantStatus = (): Promise<AssistantStatus | null> =>
  request<AssistantStatus>("/assistant/status").catch(() => null);

export const newIdempotencyKey = (): string => crypto.randomUUID();
