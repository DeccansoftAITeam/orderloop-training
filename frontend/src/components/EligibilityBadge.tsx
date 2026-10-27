import type { Eligibility } from "../api";
import { eligibilityState, stateLabel, type EligibilityState } from "../status";
import { Badge, type Tone } from "./Badge";

const stateTone: Record<EligibilityState, Tone> = {
  eligible: "green",
  late: "amber",
  ineligible: "red",
  undelivered: "grey",
};

export function EligibilityBadge({ eligibility }: { eligibility: Eligibility }) {
  const s = eligibilityState(eligibility);
  return <Badge tone={stateTone[s]}>{stateLabel[s]}</Badge>;
}
