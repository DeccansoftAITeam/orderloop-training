/** Single place where integer cents become display dollars. */
const fmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const formatCents = (cents: number): string => fmt.format(cents / 100);

/** Parse a dollar string such as "12.5" into integer cents, or null if invalid. */
export function parseDollarsToCents(input: string): number | null {
  const s = input.trim().replace(/^\$/, "");
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null;
  const [whole, frac = ""] = s.split(".");
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}
