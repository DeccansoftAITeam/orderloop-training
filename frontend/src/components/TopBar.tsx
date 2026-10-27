import type { AssistantStatus } from "../api";
import { Badge } from "./Badge";

export function TopBar({ assistant }: { assistant: AssistantStatus | null }) {
  const isAi = assistant?.provider === "claude";
  return (
    <header className="topbar">
      <div className="brand">
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" />
          <path d="M12 3a9 9 0 0 1 9 9" fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
        <span className="brand-name">OrderLoop</span>
        <span className="brand-sub">Kestrel Outfitters support</span>
      </div>
      <div className="topbar-badges">
        <Badge tone="grey">Local environment</Badge>
        {assistant && (
          <Badge tone={isAi ? "accent" : "grey"} title={assistant.model ? `Model: ${assistant.model}` : undefined}>
            {isAi ? "AI drafts" : "Template drafts"}
            {assistant.model ? ` · ${assistant.model}` : ""}
          </Badge>
        )}
      </div>
    </header>
  );
}
