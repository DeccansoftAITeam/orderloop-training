import type { Refund } from "../api";
import { formatCents } from "../money";

export function RefundHistory({ refunds }: { refunds: Refund[] }) {
  return (
    <section className="card" aria-labelledby="hist-title">
      <h3 id="hist-title" className="card-title">Refund history</h3>
      {refunds.length === 0 ? (
        <p className="empty-inline">No refunds have been issued on this order.</p>
      ) : (
        <ul className="history">
          {refunds.map((r) => (
            <li key={r.id}>
              <span className="history-amt">{formatCents(r.amount_cents)}</span>
              <span className="history-reason">{r.reason}</span>
              {r.created_at && (
                <time className="muted" dateTime={r.created_at}>
                  {new Date(r.created_at).toLocaleDateString()}
                </time>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
