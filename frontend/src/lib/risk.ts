/**
 * The only place on this site allowed to use colour.
 *
 * Risk is shown like a traffic light: green, yellow, red. The colours change
 * at the same points as the words "low", "medium" and "high", so the colour
 * and the word next to it always agree.
 *
 * Colour is never the only clue - the score and the word are always shown
 * too. That matters here, because green and red are the hardest pair to tell
 * apart for people with colour blindness. The word is what makes it safe.
 */

/** Where each level starts. Below 0.4 is "low", below 0.7 is "medium", the
 *  rest is "high". Must match RISK_BREAKS in backend/app/services/dashboard.py. */
const TIER_BREAKS = [0.4, 0.7] as const;

export type RiskStep = 0 | 1 | 2;

export const RISK_TIERS = ["low", "medium", "high"] as const;
export type RiskTier = (typeof RISK_TIERS)[number];

/* Written out in full on purpose. Tailwind only includes styles whose names
   appear in the code exactly, so building a name like `text-risk-${n}` would
   silently produce no colour at all. */
const TEXT: Record<RiskStep, string> = {
  0: "text-risk-0-text",
  1: "text-risk-1-text",
  2: "text-risk-2-text",
};

const BG: Record<RiskStep, string> = {
  0: "bg-risk-0",
  1: "bg-risk-1",
  2: "bg-risk-2",
};

export function riskStep(score: number): RiskStep {
  if (score < TIER_BREAKS[0]) return 0;
  if (score < TIER_BREAKS[1]) return 1;
  return 2;
}

/** The colour for text - chosen to be easy to read. */
export function riskText(score: number): string {
  return TEXT[riskStep(score)];
}

/** The colour for filled shapes like chart bars - chosen so the three levels
 *  are easy to tell apart, including for colour-blind readers. Use riskText()
 *  for anything with words on it. */
export function riskBgForStep(step: RiskStep): string {
  return BG[step];
}

export function riskTier(score: number): RiskTier {
  return RISK_TIERS[riskStep(score)];
}
