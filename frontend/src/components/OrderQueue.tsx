import { useEffect, useState } from "react";
import { getOrder, listOrders, type OrderDetail, type OrderSummary } from "../api";
import { formatCents } from "../money";
import { daysSince } from "../status";
import { EligibilityBadge } from "./EligibilityBadge";

interface Props {
  selected: number | null;
  onSelect: (id: number) => void;
  version: number;
}

export function OrderQueue({ selected, onSelect, version }: Props) {
  const [query, setQuery] = useState("");
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [details, setDetails] = useState<Record<number, OrderDetail>>({});

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      listOrders(query)
        .then((o) => {
          if (live) {
            setOrders(o);
            setError(false);
          }
        })
        .catch(() => {
          if (live) {
            setOrders([]);
            setError(true);
          }
        });
    }, 200);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [query, version]);

  // Eligibility is only available per order, so load it for the visible queue.
  useEffect(() => {
    if (!orders) return;
    let live = true;
    orders.forEach((o) =>
      getOrder(o.id)
        .then((d) => {
          if (live) setDetails((prev) => ({ ...prev, [o.id]: d }));
        })
        .catch(() => undefined),
    );
    return () => {
      live = false;
    };
  }, [orders, version]);

  return (
    <section className="queue" aria-label="Order queue">
      <div className="queue-head">
        <h2 className="section-title">Orders</h2>
        <label className="search">
          <span className="sr-only">Search orders by number or customer</span>
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M20 20l-4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            id="order-search"
            type="search"
            placeholder="Search order or customer"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <div className="queue-list">
        {orders === null && (
          <div aria-busy="true">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton queue-skel" />
            ))}
          </div>
        )}
        {orders && error && <p className="empty">Could not load orders. Check that the API is running.</p>}
        {orders && !error && orders.length === 0 && (
          <p className="empty">No orders match "{query}". Try an order number or a customer name.</p>
        )}
        {orders && orders.length > 0 && (
          <ul className="order-list">
            {orders.map((o) => {
              const d = details[o.id];
              const days = daysSince(o.delivered_at);
              return (
                <li key={o.id}>
                  <button
                    type="button"
                    className="order-row"
                    aria-current={o.id === selected ? "true" : undefined}
                    onClick={() => onSelect(o.id)}
                  >
                    <span className="row-top">
                      <span className="order-id">#{o.id}</span>
                      <span className="row-total">{formatCents(o.total_cents)}</span>
                    </span>
                    <span className="row-name">{o.customer_name}</span>
                    <span className="row-meta">
                      <span className="chip">{o.status}</span>
                      <span className="muted">{days === null ? "Awaiting delivery" : `Delivered ${days}d ago`}</span>
                      <span className="row-badge">
                        {d ? <EligibilityBadge eligibility={d.eligibility} /> : <span className="skeleton badge-skel" />}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
