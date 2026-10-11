import type { DashboardRiskMix } from "../api/types";
import { formatCount, formatRate } from "../lib/format";
import { riskBgForStep, type RiskStep } from "../lib/risk";

/**
 * A bar showing how the period's orders split into low, medium and high risk.
 *
 * The only coloured thing on this page. The colour classes are written out in
 * full in lib/risk.ts, never pieced together. Tailwind finds classes by
 * reading the source code, so a class built at runtime like `bg-risk-${n}`
 * never gets created, and the colour is just silently missing.
 *
 * Screen readers skip the bar itself. The counts are printed next to it with
 * the words Low, Medium and High, because green and red are the colours
 * colour-blind people most often mix up - colour is never the only clue.
 */
const BANDS: { step: RiskStep; label: string; key: keyof DashboardRiskMix }[] = [
  { step: 0, label: "Low", key: "low" },
  { step: 1, label: "Medium", key: "medium" },
  { step: 2, label: "High", key: "high" },
];

export default function RiskMixBar({ mix, total }: { mix: DashboardRiskMix; total: number }) {
  // No orders, so nothing to show. The section's "no orders" message is
  // shown instead of an empty bar.
  if (total <= 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex h-3 overflow-hidden rounded-[2px]" aria-hidden="true">
        {BANDS.map(({ step, key }) => {
          const count = mix[key];
          if (count <= 0) return null;
          return (
            <div
              key={key}
              className={riskBgForStep(step)}
              style={{ width: `${(count / total) * 100}%` }}
            />
          );
        })}
      </div>
      <dl className="flex flex-wrap gap-x-10 gap-y-2">
        {BANDS.map(({ step, label, key }) => (
          <div key={key} className="flex items-baseline gap-1.5">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-[2px] ${riskBgForStep(step)}`} aria-hidden="true" />
            <dt className="font-condensed text-body text-ink-muted">{label}</dt>
            <dd className="text-head tabular-nums">
              {formatCount(mix[key])}
              <span className="text-body text-ink-muted"> ({formatRate(mix[key] / total)})</span>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
