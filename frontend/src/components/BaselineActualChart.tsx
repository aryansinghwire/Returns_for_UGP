/**
 * Only used by ReportingPage, which is switched off at the moment. This only
 * shows up if the reporting page is turned back on.
 */
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ReportingBucket } from "../api/types";
import { TH } from "../lib/controls";
import { formatCount, formatRate } from "../lib/format";

const ACTUAL = "Actual outcome rate";
const BASELINE = "Historical baseline";

/**
 * Two sets of return rates on one chart: what actually happened, and the
 * usual rate it's compared with.
 *
 * Black, white and grey only. In this app colour means risk, and neither of
 * these is a risk score. So they're told apart by shape instead - a solid bar
 * for what happened, a dashed line for the usual rate. That also works for
 * colour-blind readers and when printed.
 *
 * Colours come from the CSS variables, not written-in values. The chart
 * library takes colours as settings, so Tailwind's dark-mode styles can't
 * reach it, and a fixed colour would leave dark text on a dark page in dark
 * mode.
 */
export default function BaselineActualChart({ buckets }: { buckets: ReportingBucket[] }) {
  if (buckets.length === 0) {
    return <p className="text-body text-ink-muted">No data for this selection.</p>;
  }

  const data = buckets.map((b) => ({
    bucket: b.bucket,
    [ACTUAL]: Number((b.actual_return_rate * 100).toFixed(1)),
    [BASELINE]: Number((b.baseline_return_rate * 100).toFixed(1)),
    n: b.n_orders,
  }));

  return (
    <figure className="m-0" aria-labelledby="chart-title">
      {/* The chart needs a name for screen readers. The "View as table"
          section below can't provide it: it contains the whole table, so the
          name would be "View as table" followed by every cell. */}
      <figcaption id="chart-title" className="sr-only">
        Actual outcome rate against historical baseline, by period
      </figcaption>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke="var(--rule)" vertical={false} />
            <XAxis
              dataKey="bucket"
              tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
              stroke="var(--rule)"
            />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
              stroke="var(--rule)"
              unit="%"
              width={44}
            />
            <Tooltip
              cursor={{ fill: "var(--panel)" }}
              contentStyle={{
                backgroundColor: "var(--paper)",
                border: "1px solid var(--rule)",
                borderRadius: 2,
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--ink)" }}
              itemStyle={{ color: "var(--ink-muted)" }}
              formatter={(value, name) => [`${value}%`, String(name)]}
              labelFormatter={(label, payload) => {
                const n = payload?.[0]?.payload?.n;
                return n !== undefined ? `${label} (n=${formatCount(Number(n))})` : String(label);
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: "var(--ink-muted)" }} />
            <Bar dataKey={ACTUAL} fill="var(--ink)" radius={[2, 2, 0, 0]} maxBarSize={40} />
            <Line
              type="monotone"
              dataKey={BASELINE}
              stroke="var(--ink-muted)"
              strokeWidth={2}
              dot={false}
              strokeDasharray="6 4"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Screen readers can't read the chart. This is the same numbers as a
          table, which can be read aloud, searched and copied. */}
      <div className="mt-2">
        <details className="text-body">
          <summary className="cursor-pointer font-condensed text-meta text-ink-muted hover:text-ink">
            View as table
          </summary>
          <table className="mt-2 w-full border-collapse text-body">
            <thead className="text-left">
              <tr className="border-b border-rule">
                <th scope="col" className={`${TH} px-2 py-1`}>Period</th>
                <th scope="col" className={`${TH} px-2 py-1`}>{ACTUAL}</th>
                <th scope="col" className={`${TH} px-2 py-1`}>{BASELINE}</th>
                <th scope="col" className={`${TH} px-2 py-1`}>Orders</th>
              </tr>
            </thead>
            <tbody>
              {buckets.map((b) => (
                <tr key={b.bucket} className="border-b border-rule/60">
                  <th scope="row" className="px-2 py-1 text-left font-normal">{b.bucket}</th>
                  <td className="px-2 py-1 tabular-nums">{formatRate(b.actual_return_rate)}</td>
                  <td className="px-2 py-1 tabular-nums">{formatRate(b.baseline_return_rate)}</td>
                  <td className="px-2 py-1 tabular-nums">{formatCount(b.n_orders)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </div>
    </figure>
  );
}
