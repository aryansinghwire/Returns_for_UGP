import { riskText, riskTier } from "../lib/risk";

const TIER_LABELS = { low: "low", medium: "med", high: "high" } as const;

/**
 * An order's risk score, shown as the most eye-catching thing in its row.
 *
 * It used to be a small, pale label that drew less attention than the column
 * heading above it - even though the score is the main thing this product
 * exists to show. Now it's the biggest text in the row, with every digit the
 * same width so the decimal points line up down the page. It's coloured by
 * risk level, which is the only use of colour in the app.
 *
 * The word next to it (low, medium or high) says the same thing as the
 * colour, so nothing depends on colour alone.
 */
export default function ScoreBadge({
  score,
  size = "md",
}: {
  score: number;
  size?: "sm" | "md";
}) {
  const tier = riskTier(score);
  return (
    <span className="inline-flex items-baseline gap-1.5 whitespace-nowrap">
      <span
        className={`font-medium tabular-nums ${riskText(score)} ${
          size === "sm" ? "text-head" : "text-display"
        }`}
      >
        {score.toFixed(2)}
      </span>
      <span className="font-condensed text-meta text-ink-muted">{TIER_LABELS[tier]}</span>
    </span>
  );
}
