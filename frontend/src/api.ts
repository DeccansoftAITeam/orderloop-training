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
  total_cents: number;
  refundable: boolean;
}

export interface OrderDetail {
  id: number;
  status: string;
  customer: { id: number; name: string };
  items: OrderItem[];
  refunds: { id: number; amount_cents: number; reason: string }[];
  eligibility: {
    eligible: boolean;
    late: boolean;
    days_since_delivery: number | null;
    max_refundable_cents: number;
    blockers: string[];
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail?.message ?? `Request failed (${res.status})`);
  return body as T;
}

export const listOrders = (q: string) => request<OrderSummary[]>(`/orders?q=${encodeURIComponent(q)}`);
export const getOrder = (id: number) => request<OrderDetail>(`/orders/${id}`);

export const createRefund = (id: number, amountCents: number, reason: string) =>
  request(`/orders/${id}/refunds`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ amount_cents: amountCents, reason }),
  });

export const draftReply = (id: number, message: string) =>
  request<{ draft: string }>(`/orders/${id}/reply-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
