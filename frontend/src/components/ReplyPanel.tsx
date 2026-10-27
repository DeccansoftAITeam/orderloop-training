import { useState } from "react";
import { draftReply, type ReplyDraft } from "../api";
import { Badge } from "./Badge";

export function ReplyPanel({ orderId }: { orderId: number }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ReplyDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      setResult(await draftReply(orderId, message));
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Could not draft a reply.");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.draft);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("The browser blocked copying. Select the text and copy it manually.");
    }
  }

  return (
    <section className="card" aria-labelledby="reply-title">
      <h3 id="reply-title" className="card-title">Reply to customer</h3>
      <div className="field">
        <label htmlFor="customer-message">Customer message</label>
        <textarea
          id="customer-message"
          rows={4}
          value={message}
          placeholder="Paste what the customer wrote."
          onChange={(e) => setMessage(e.target.value)}
          aria-describedby="mask-note"
        />
        <p id="mask-note" className="help">Personal details are masked before drafting.</p>
      </div>
      <div className="form-actions">
        <button type="button" className="btn primary" onClick={run} disabled={busy || message.trim() === ""} aria-busy={busy}>
          {busy && <span className="spinner" aria-hidden="true" />}
          {busy ? "Drafting" : "Draft reply"}
        </button>
        {message.trim() === "" && <span className="muted">Paste the customer's message to enable drafting.</span>}
      </div>
      <div aria-live="polite">
        {busy && (
          <div className="draft" aria-label="Drafting reply">
            <div className="skeleton line" />
            <div className="skeleton line" />
            <div className="skeleton line short" />
          </div>
        )}
        {!busy && error && (
          <p className="note note-red" role="alert">{error}</p>
        )}
        {!busy && result && (
          <div className="draft">
            <div className="draft-head">
              <span className="draft-label">Draft</span>
              {result.provider && (
                <Badge tone={result.provider === "claude" ? "accent" : "grey"} title={result.model}>
                  {result.provider === "claude" ? "AI draft" : "Template"}
                </Badge>
              )}
              <button type="button" className="btn small ghost push" onClick={copy}>
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <p className="draft-text">{result.draft}</p>
          </div>
        )}
      </div>
    </section>
  );
}
