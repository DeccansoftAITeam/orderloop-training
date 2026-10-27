import { useCallback, useEffect, useState } from "react";
import { getAssistantStatus, type AssistantStatus } from "./api";
import { OrderDetailPane } from "./components/OrderDetailPane";
import { OrderQueue } from "./components/OrderQueue";
import { Toasts, type Toast } from "./components/Toasts";
import { TopBar } from "./components/TopBar";

let nextToast = 1;

export default function App() {
  const [selected, setSelected] = useState<number | null>(null);
  const [assistant, setAssistant] = useState<AssistantStatus | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    void getAssistantStatus().then(setAssistant);
  }, []);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback(
    (kind: Toast["kind"], text: string) => {
      const id = nextToast++;
      setToasts((t) => [...t, { id, kind, text }]);
      setTimeout(() => dismiss(id), kind === "error" ? 8000 : 4500);
    },
    [dismiss],
  );

  return (
    <div className="shell">
      <TopBar assistant={assistant} />
      <main className={`panes${selected !== null ? " has-selection" : ""}`}>
        <OrderQueue selected={selected} onSelect={setSelected} version={version} />
        <div className="detail-pane">
          {selected === null ? (
            <div className="empty-state">
              <h2>Select an order</h2>
              <p className="muted">Pick an order from the queue to review eligibility, issue a refund or draft a reply.</p>
            </div>
          ) : (
            <OrderDetailPane
              id={selected}
              onBack={() => setSelected(null)}
              onRefunded={(m) => {
                push("success", m);
                setVersion((v) => v + 1);
              }}
              onError={(m) => push("error", m)}
            />
          )}
        </div>
      </main>
      <Toasts toasts={toasts} dismiss={dismiss} />
    </div>
  );
}
