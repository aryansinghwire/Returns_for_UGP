/**
 * The list of orders handed to a company admin. Each row is an "escalate"
 * action from intervention_log, and whether it's open or resolved comes from
 * that same row. There's no separate escalations table - see
 * backend/app/services/escalations.py for why.
 */
import { Link } from "react-router-dom";
import { ROLE_LABELS, type EscalationOut } from "../api/types";
import { LINK } from "../lib/controls";
import { formatDate, formatDateTime } from "../lib/format";
import ScoreBadge from "./ScoreBadge";

export default function EscalationsTable({
  escalations,
  showingResolved,
}: {
  escalations: EscalationOut[];
  showingResolved: boolean;
}) {
  if (escalations.length === 0) {
    return (
      <p className="text-body text-ink-muted">
        {showingResolved
          ? "Nothing has been escalated for this tenant yet."
          : "No open escalations. Analysts hand an order up from its detail page; it appears here until someone records an outcome."}
      </p>
    );
  }

  return (
    <div className="overflow-auto rounded-[4px] border border-rule">
      <table className="w-full border-collapse text-body">
        <caption className="sr-only">
          Orders an analyst escalated to the tenant admin, newest first
        </caption>
        <thead className="bg-panel text-left text-meta uppercase tracking-wide text-ink-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Order</th>
            <th scope="col" className="px-3 py-2 font-medium">Score</th>
            <th scope="col" className="px-3 py-2 font-medium">Raised by</th>
            <th scope="col" className="px-3 py-2 font-medium">Raised</th>
            <th scope="col" className="px-3 py-2 font-medium">Reason given</th>
            <th scope="col" className="px-3 py-2 font-medium">Status</th>
            <th scope="col" className="px-3 py-2 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {escalations.map((e) => (
            /* Keyed by the action, not the order, because the same order
               can be escalated more than once. */
            <tr key={e.log_id} className="border-t border-rule">
              <th scope="row" className="px-3 py-2 text-left font-normal">
                <span className="font-mono text-meta" translate="no">{e.order_id}</span>
                <span className="block font-condensed text-meta text-ink-muted">
                  {e.tenant} · ordered {formatDate(e.order_date)}
                </span>
              </th>
              <td className="px-3 py-2">
                <ScoreBadge score={e.current_score} size="sm" />
              </td>
              <td className="px-3 py-2">
                {e.trigger === "automated_threshold" ? (
                  <span className="text-ink-muted">Automated rule</span>
                ) : (
                  <>
                    {e.raised_by ?? "—"}
                    <span className="block font-condensed text-meta text-ink-muted">
                      {ROLE_LABELS[e.raised_by_role] ?? e.raised_by_role}
                    </span>
                  </>
                )}
              </td>
              <td className="px-3 py-2 whitespace-nowrap tabular-nums">
                {formatDateTime(e.raised_at)}
              </td>
              {/* The note explains why the order was handed over, so it gets the most space. */}
              <td className="px-3 py-2 text-ink-muted">
                {e.note ?? <span className="italic">No reason given</span>}
              </td>
              <td className="px-3 py-2">
                {e.outcome === "pending" ? (
                  <span className="font-condensed text-meta font-semibold uppercase">Open</span>
                ) : (
                  <span className="font-condensed text-meta text-ink-muted">
                    {(e.outcome ?? "").replace(/_/g, " ")}
                  </span>
                )}
              </td>
              <td className="px-3 py-2">
                <Link to={`/orders/${e.order_id}`} className={`text-meta ${LINK}`}>
                  Review
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
