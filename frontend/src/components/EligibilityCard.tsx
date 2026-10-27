import type { Eligibility } from "../api";
import { formatCents } from "../money";
import { describeBlocker, eligibilityState, stateLabel } from "../status";

const headline = {
  eligible: "Within the 30-day refund window",
  late: "Past the 30-day window",
  ineligible: "Nothing can be refunded",
  undelivered: "Waiting on delivery",
} as const;

export function EligibilityCard({ eligibility: el }: { eligibility: Eligibility }) {
  const s = eligibilityState(el);
  return (
    <section className={`card elig elig-${s}`} aria-labelledby="elig-title">
      <div className="elig-head">
        <span className="elig-dot" aria-hidden="true" />
        <div>
          <h3 id="elig-title" className="card-title">{stateLabel[s]}</h3>
          <p className="muted">{headline[s]}</p>
        </div>
      </div>
      <dl className="stats">
        <div>
          <dt>Max refundable</dt>
          <dd>{formatCents(el.max_refundable_cents)}</dd>
        </div>
        <div>
          <dt>Days since delivery</dt>
          <dd>{el.days_since_delivery ?? "None"}</dd>
        </div>
        {typeof el.restocking_fee_cents === "number" && el.restocking_fee_cents > 0 && (
          <div>
            <dt>Restocking fee</dt>
            <dd>{formatCents(el.restocking_fee_cents)}</dd>
          </div>
        )}
      </dl>
      {el.late && el.eligible && (
        <p className="note note-amber">This order is past the window. Confirm the exception with a lead before refunding.</p>
      )}
      {el.blockers.length > 0 && (
        <ul className="blockers" aria-label="Blockers">
          {el.blockers.map((b) => (
            <li key={b}>{describeBlocker(b)}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
