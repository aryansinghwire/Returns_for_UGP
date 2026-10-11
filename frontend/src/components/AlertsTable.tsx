/**
 * Alerts for one company, or for all of them. Each row is a group of orders
 * (one product, country or product type) whose recent return rate is far
 * enough above its usual rate to be worth a look. It's about the group, not
 * any single order. The thresholds are in backend/app/config.py.
 */
import { Link } from "react-router-dom";
import { SEVERITY_LABELS, type AlertOut } from "../api/types";
import { LINK } from "../lib/controls";
import { formatCount, formatPercentagePoints, formatRate } from "../lib/format";

function queueLink(alert: AlertOut): string {
  if (alert.cohort_type === "country") return `/queue?country=${encodeURIComponent(alert.cohort_key)}`;
  if (alert.cohort_type === "product_type") return `/queue?product_type=${encodeURIComponent(alert.cohort_key)}`;
  return "/queue";
}

export default function AlertsTable({ alerts }: { alerts: AlertOut[] }) {
  if (alerts.length === 0) {
    return (
      <p className="text-body text-ink-muted">
        No spikes detected — all cohorts are within their historical baseline (or don&rsquo;t yet
        have enough recent orders to evaluate).
      </p>
    );
  }

  return (
    <div className="overflow-auto rounded-[4px] border border-rule">
      <table className="w-full border-collapse text-body">
        <caption className="sr-only">
          Cohorts whose recent return rate exceeds their historical baseline
        </caption>
        <thead className="bg-panel text-left text-meta uppercase tracking-wide text-ink-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Severity</th>
            <th scope="col" className="px-3 py-2 font-medium">Tenant</th>
            <th scope="col" className="px-3 py-2 font-medium">Cohort</th>
            <th scope="col" className="px-3 py-2 font-medium">Baseline</th>
            <th scope="col" className="px-3 py-2 font-medium">Recent actual</th>
            <th scope="col" className="px-3 py-2 font-medium">Gap</th>
            <th scope="col" className="px-3 py-2 font-medium">n (recent)</th>
            <th scope="col" className="px-3 py-2 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => (
            /* The key combines company and group, because the server sends one
               row for each pair. Keying by position would mix rows up whenever
               the list changes. */
            <tr
              key={`${a.tenant}:${a.cohort_type}:${a.cohort_key}`}
              className="border-t border-rule"
            >
              <td className="px-3 py-2">
                {/* An alert's severity is about return risk too, so it uses
                    the same risk colours as the order list instead of a new
                    set of colours. */}
                <span
                  className={`rounded-[2px] border border-rule px-1.5 py-px font-condensed text-meta font-semibold ${
                    a.severity === "high" ? "text-risk-2-text" : "text-risk-1-text"
                  }`}
                >
                  {SEVERITY_LABELS[a.severity] ?? a.severity}
                </span>
              </td>
              <td className="px-3 py-2">{a.tenant}</td>
              <th scope="row" className="px-3 py-2 text-left font-mono text-meta font-normal" translate="no">
                {a.cohort_type}: {a.cohort_key}
              </th>
              <td className="px-3 py-2 tabular-nums">{formatRate(a.baseline_rate)}</td>
              <td className="px-3 py-2 tabular-nums">{formatRate(a.actual_rate)}</td>
              <td className="px-3 py-2 font-medium tabular-nums">{formatPercentagePoints(a.gap)}</td>
              <td className="px-3 py-2 tabular-nums">{formatCount(a.n_orders)}</td>
              <td className="px-3 py-2">
                <Link to={queueLink(a)} className={`text-meta ${LINK}`}>
                  View Queue
                  <span aria-hidden="true"> →</span>
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
