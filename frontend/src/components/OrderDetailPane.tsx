import { useCallback, useEffect, useState } from "react";
import { getOrder, type OrderDetail } from "../api";
import { daysSince, eligibilityState } from "../status";
import { Badge } from "./Badge";
import { EligibilityCard } from "./EligibilityCard";
import { ItemsTable } from "./ItemsTable";
import { RefundForm } from "./RefundForm";
import { RefundHistory } from "./RefundHistory";
import { ReplyPanel } from "./ReplyPanel";

interface Props {
  id: number;
  onBack: () => void;
  onRefunded: (msg: string) => void;
  onError: (msg: string) => void;
}

export function OrderDetailPane({ id, onBack, onRefunded, onError }: Props) {
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const load = useCallback(
    () =>
      getOrder(id)
        .then((o) => {
          setOrder(o);
          setFailed(null);
        })
        .catch((e: Error) => setFailed(e.message)),
    [id],
  );

  useEffect(() => {
    setOrder(null);
    setFailed(null);
    void load();
  }, [load]);

  if (failed) {
    return <p className="empty" role="alert">{failed}</p>;
  }
  if (!order) {
    return (
      <div className="detail" aria-busy="true">
        <div className="skeleton line title" />
        <div className="skeleton block" />
        <div className="skeleton block" />
      </div>
    );
  }
  const state = eligibilityState(order.eligibility);
  const days = daysSince(order.delivered_at ?? null);

  return (
    <article className="detail" aria-label={`Order ${order.id}`}>
      <button type="button" className="btn ghost small back" onClick={onBack}>
        Back to orders
      </button>
      <header className="detail-head">
        <div>
          <h2 className="detail-title">Order #{order.id}</h2>
          <p className="muted">
            {order.customer.name}
            {days !== null ? ` · delivered ${days} days ago` : " · not yet delivered"}
          </p>
        </div>
        <Badge tone="grey">{order.status.charAt(0).toUpperCase() + order.status.slice(1)}</Badge>
      </header>
      <EligibilityCard eligibility={order.eligibility} />
      <section className="card" aria-labelledby="items-title">
        <h3 id="items-title" className="card-title">Items</h3>
        <ItemsTable items={order.items} />
      </section>
      <div className="two-col">
        <RefundForm
          key={order.id}
          orderId={order.id}
          maxCents={order.eligibility.max_refundable_cents}
          disabled={state === "ineligible" || state === "undelivered"}
          onDone={(m) => {
            onRefunded(m);
            void load();
          }}
          onError={onError}
        />
        <RefundHistory refunds={order.refunds} />
      </div>
      <ReplyPanel key={order.id} orderId={order.id} initialMessage={order.customer_message ?? ""} />
    </article>
  );
}
