import { useRef, useState, type FormEvent } from "react";
import { createRefund, newIdempotencyKey } from "../api";
import { formatCents, parseDollarsToCents } from "../money";

interface Props {
  orderId: number;
  maxCents: number;
  disabled: boolean;
  onDone: (msg: string) => void;
  onError: (msg: string) => void;
}

const MIN = 3;
const MAX = 200;

export function RefundForm({ orderId, maxCents, disabled, onDone, onError }: Props) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  // One key per distinct attempt; the same payload retried reuses its key.
  const attempt = useRef<{ sig: string; key: string } | null>(null);

  const cents = parseDollarsToCents(amount);
  const trimmed = reason.trim().length;
  let amountError: string | null = null;
  if (amount.trim() === "") amountError = "Enter an amount.";
  else if (cents === null) amountError = "Use dollars and cents, such as 24.50.";
  else if (cents <= 0) amountError = "Amount must be more than $0.00.";
  else if (cents > maxCents) amountError = `Amount cannot exceed ${formatCents(maxCents)}.`;
  const reasonError =
    trimmed < MIN
      ? `Reason needs at least ${MIN} characters.`
      : reason.length > MAX
        ? `Reason must be ${MAX} characters or fewer.`
        : null;
  const invalid = amountError !== null || reasonError !== null;
  const showAmountErr = amountError !== null && (touched || amount !== "");
  const showReasonErr = reasonError !== null && (touched || reason !== "");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (invalid || cents === null || busy) return;
    const sig = `${cents}|${reason.trim()}`;
    if (attempt.current?.sig !== sig) attempt.current = { sig, key: newIdempotencyKey() };
    setBusy(true);
    try {
      await createRefund(orderId, cents, reason.trim(), attempt.current.key);
      attempt.current = null;
      setAmount("");
      setReason("");
      setTouched(false);
      onDone(`Refund of ${formatCents(cents)} recorded.`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Refund failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="refund-title">
      <h3 id="refund-title" className="card-title">Issue a refund</h3>
      <form onSubmit={submit} noValidate className="form">
        <div className="field">
          <label htmlFor="refund-amount">Amount (USD)</label>
          <div className={`input-affix${showAmountErr ? " invalid" : ""}`}>
            <span aria-hidden="true">$</span>
            <input
              id="refund-amount"
              inputMode="decimal"
              autoComplete="off"
              placeholder="0.00"
              value={amount}
              disabled={disabled}
              aria-invalid={showAmountErr ? true : undefined}
              aria-describedby="refund-amount-help"
              onChange={(e) => setAmount(e.target.value)}
            />
            <button
              type="button"
              className="link"
              disabled={disabled || maxCents === 0}
              onClick={() => setAmount((maxCents / 100).toFixed(2))}
            >
              Use max
            </button>
          </div>
          <p id="refund-amount-help" className={showAmountErr ? "help err" : "help"}>
            {showAmountErr ? amountError : `Up to ${formatCents(maxCents)} available.`}
          </p>
        </div>
        <div className="field">
          <label htmlFor="refund-reason">Reason</label>
          <textarea
            id="refund-reason"
            rows={3}
            value={reason}
            disabled={disabled}
            aria-invalid={showReasonErr ? true : undefined}
            aria-describedby="refund-reason-help"
            onChange={(e) => setReason(e.target.value)}
          />
          <p id="refund-reason-help" className={showReasonErr ? "help err split" : "help split"}>
            <span>{showReasonErr ? reasonError : "Saved on the refund record."}</span>
            <span className={reason.length > MAX ? "err" : ""}>
              {reason.length}/{MAX}
            </span>
          </p>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn primary" disabled={disabled || busy} aria-busy={busy}>
            {busy && <span className="spinner" aria-hidden="true" />}
            {busy ? "Submitting" : "Submit refund"}
          </button>
          {disabled && <span className="muted">Refunds are unavailable for this order.</span>}
        </div>
      </form>
    </section>
  );
}
