import type { Eligibility } from "./api";

export type EligibilityState = "eligible" | "late" | "ineligible" | "undelivered";

export const stateLabel: Record<EligibilityState, string> = {
  eligible: "Eligible",
  late: "Late",
  ineligible: "Ineligible",
  undelivered: "Not delivered",
};

export function eligibilityState(el: Eligibility): EligibilityState {
  if (el.blockers.includes("not_delivered")) return "undelivered";
  if (!el.eligible) return "ineligible";
  return el.late ? "late" : "eligible";
}

const blockerText: Record<string, string> = {
  not_delivered: "The order has not been delivered yet.",
  no_refundable_items: "Every item is final sale or a gift card.",
  nothing_left_to_refund: "The refundable total has already been refunded.",
};
export const describeBlocker = (b: string): string => blockerText[b] ?? b.replace(/_/g, " ");

export function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  const t = new Date();
  const ms =
    Date.UTC(t.getFullYear(), t.getMonth(), t.getDate()) -
    Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
  return Math.floor(ms / 86_400_000);
}
