import type { ScoreHistogram } from "../api/types";
import { formatCount, pluralize } from "../lib/format";
import { riskBgForStep, riskStep } from "../lib/risk";
import ScoreRangeSlider from "./ScoreRangeSlider";

/**
 * A small bar chart of how many orders there are at each risk score, with the
 * user's chosen score range marked on it.
 *
 * It replaced the Min and Max score boxes that used to be in the filter bar.
 * A number typed into a box doesn't tell you how many orders you're cutting
 * out. The chart shows where the orders actually are, so choosing 0.80–1.00
 * means seeing exactly which orders you're picking.
 *
 * Bars outside the chosen range are faded, not hidden - the point is to see
 * what you're leaving out.
 *
 * The range is set with the two-handle slider underneath, not by dragging
 * across the bars. It uses the same 0-1 scale, lines up with the chart, and
 * already works with a keyboard. A custom drag tool would have to rebuild
 * all of that and would probably get it wrong.
 */
export default function RiskDistribution({
  data,
  isLoading,
  min,
  max,
  onChange,
  onCommit,
}: {
  data: ScoreHistogram | undefined;
  isLoading: boolean;
  min: number;
  max: number;
  onChange: (next: { min: number; max: number }) => void;
  onCommit?: () => void;
}) {
  const buckets = data?.buckets ?? [];
  const peak = buckets.reduce((acc, b) => Math.max(acc, b.count), 0);
  const selected = buckets
    .filter((b) => b.upper > min && b.lower < max)
    .reduce((sum, b) => sum + b.count, 0);

  return (
    <section
      aria-labelledby="risk-distribution-heading"
      className="border-b border-rule bg-panel px-4 py-3"
    >
      {/* h3, because this is part of the order list page, whose heading is the h2. */}
      <h3 id="risk-distribution-heading" className="sr-only">
        Score distribution and window
      </h3>

      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div className="min-w-64 flex-1">
          {/* Each bar's height is the number of orders. Its colour is the risk
              level for that score, the same colours as the table below. */}
          <div className="flex h-12 items-end gap-px" aria-hidden="true">
            {buckets.length === 0
              ? Array.from({ length: 20 }, (_, i) => (
                  <div key={i} className="h-px flex-1 bg-rule" />
                ))
              : buckets.map((b) => {
                  const inWindow = b.upper > min && b.lower < max;
                  return (
                    <div
                      key={b.lower}
                      /* A bar with any orders in it is never drawn as nothing.
                         Even a few orders get a visible bar, so you can see
                         they're there. */
                      style={{ height: b.count === 0 ? 1 : `${Math.max(4, (b.count / peak) * 100)}%` }}
                      className={`flex-1 ${
                        b.count === 0
                          ? "bg-rule"
                          : `${riskBgForStep(riskStep((b.lower + b.upper) / 2))} ${
                              inWindow ? "" : "opacity-25"
                            }`
                      }`}
                    />
                  );
                })}
          </div>

          <ScoreRangeSlider
            label="Score window"
            min={min}
            max={max}
            onChange={onChange}
            onCommit={onCommit}
            className="mt-1 w-full"
          />
        </div>

        <dl className="flex gap-8 text-body">
          <div>
            <dt className="font-condensed text-meta text-ink-muted">In window</dt>
            <dd className="text-head tabular-nums">
              {isLoading && !data ? "—" : formatCount(selected)}
            </dd>
          </div>
          <div>
            <dt className="font-condensed text-meta text-ink-muted">Whole queue</dt>
            <dd className="text-head tabular-nums text-ink-muted">
              {isLoading && !data ? "—" : formatCount(data?.total ?? 0)}
            </dd>
          </div>
        </dl>
      </div>

      {/* role="status" makes screen readers announce the new count when the
          range changes - otherwise the number on screen changes silently. It
          waits for a pause, so someone moving the slider with the keyboard
          hears where they stopped, not every step on the way. */}
      <p role="status" className="sr-only">
        {pluralize(selected, "order")} of {formatCount(data?.total ?? 0)} fall inside the current
        score window.
      </p>
    </section>
  );
}
