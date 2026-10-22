import { useEffect, useState } from "react";
import { OrderDetail, OrderSummary, createRefund, draftReply, getOrder, listOrders } from "./api";

const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`;

export default function App() {
  const [query, setQuery] = useState("");
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    listOrders(query).then(setOrders).catch(() => setOrders([]));
  }, [query]);

  return (
    <main>
      <h1>OrderLoop</h1>
      <div className="layout">
        <section>
          <input
            placeholder="Search order number or customer"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <table>
            <thead>
              <tr><th>Order</th><th>Customer</th><th>Total</th><th>Status</th></tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className={o.id === selected ? "active" : ""} onClick={() => setSelected(o.id)}>
                  <td>{o.id}</td><td>{o.customer_name}</td><td>{dollars(o.total_cents)}</td><td>{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section>{selected ? <OrderPanel id={selected} /> : <p>Select an order.</p>}</section>
      </div>
    </main>
  );
}

function OrderPanel({ id }: { id: number }) {
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState("");

  const reload = () => getOrder(id).then(setOrder);
  useEffect(() => { setNotice(""); setDraft(""); reload(); }, [id]);

  if (!order) return <p>Loading...</p>;
  const el = order.eligibility;

  const submit = async () => {
    try {
      await createRefund(id, Math.round(Number(amount) * 100), reason);
      setNotice("Refund recorded.");
      setAmount(""); setReason("");
      await reload();
    } catch (e) {
      setNotice((e as Error).message);
    }
  };

  return (
    <div>
      <h2>Order {order.id} for {order.customer.name}</h2>
      <ul>
        {order.items.map((i) => (
          <li key={i.sku}>{i.name} x{i.qty} - {dollars(i.total_cents)} {i.refundable ? "" : "(not refundable)"}</li>
        ))}
      </ul>
      <p>
        {el.eligible ? `Refundable up to ${dollars(el.max_refundable_cents)}` : `Not eligible: ${el.blockers.join(", ")}`}
        {el.late ? " (late)" : ""}
      </p>
      <h3>Refund</h3>
      <input placeholder="Amount in dollars" value={amount} onChange={(e) => setAmount(e.target.value)} />
      <input placeholder="Reason (3-200 characters)" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button onClick={submit}>Refund</button>
      {notice && <p role="status">{notice}</p>}
      <h3>Reply to customer</h3>
      <textarea placeholder="Paste the customer's message" value={message} onChange={(e) => setMessage(e.target.value)} />
      <button onClick={() => draftReply(id, message).then((r) => setDraft(r.draft))}>Draft reply</button>
      {draft && <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={8} />}
    </div>
  );
}
