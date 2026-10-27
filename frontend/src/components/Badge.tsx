import type { ReactNode } from "react";

export type Tone = "green" | "amber" | "red" | "grey" | "accent";

export function Badge({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {children}
    </span>
  );
}
