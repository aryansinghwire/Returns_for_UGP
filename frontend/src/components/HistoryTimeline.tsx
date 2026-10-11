/**
 * Everything done to one order, oldest first: score overrides, actions, and
 * the outcomes recorded for them. It comes from intervention_log, which is
 * only ever added to, so it's the full history. The order's current state is
 * in order_status, which only says what happened last.
 */
import { useId, useState } from "react";
import { useUpdateActionOutcome } from "../api/hooks";
import { OUTCOMES, OUTCOME_LABELS, type HistoryEntry, type Outcome } from "../api/types";
import { BUTTON_SMALL, CONTROL } from "../lib/controls";
import { formatDateTime } from "../lib/format";

function OutcomeEditor({ orderId, logId }: { orderId: string; logId: number }) {
  const id = useId();
  const [outcome, setOutcome] = useState<Outcome>("resolved_kept");
  const mutation = useUpdateActionOutcome(orderId);

  return (
    <div className="mt-1 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        {/* The "Outcome:" text above labels the current value, not this
            dropdown, so the dropdown has its own label. */}
        <label htmlFor={`${id}-outcome`} className="sr-only">
          Record the outcome of this action
        </label>
        <select
          id={`${id}-outcome`}
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as Outcome)}
          className={`${CONTROL} px-1.5 py-0.5 text-meta`}
        >
          {OUTCOMES.filter((o) => o !== "pending").map((o) => (
            <option key={o} value={o}>{OUTCOME_LABELS[o]}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => mutation.mutate({ logId, body: { outcome } })}
          disabled={mutation.isPending}
          className={`${BUTTON_SMALL} py-0.5`}
        >
          {mutation.isPending ? "Recording…" : "Record outcome"}
        </button>
      </div>
      <div aria-live="polite">
        {mutation.isError && (
          <p role="alert" className="text-meta text-alarm">
            Could not record the outcome: {(mutation.error as Error).message}. Try again.
          </p>
        )}
      </div>
    </div>
  );
}

export default function HistoryTimeline({ orderId, entries }: { orderId: string; entries: HistoryEntry[] }) {
  if (entries.length === 0) {
    return <p className="text-body text-ink-muted">No actions or overrides logged yet.</p>;
  }

  return (
    <ol className="space-y-3">
      {entries.map((e) => (
        <li key={e.id} className="rounded-[4px] border border-rule p-2.5 text-body">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-ink">
              {e.event_type === "override" ? "Score override" : (e.action_type ?? "Action")}
            </span>
            <time
              dateTime={e.created_at}
              className="shrink-0 text-meta tabular-nums text-ink-muted"
            >
              {formatDateTime(e.created_at)}
            </time>
          </div>
          <p className="text-meta text-ink-muted">
            by {e.actor_name || e.actor_role} ({e.actor_role}) · {e.trigger === "automated_threshold" ? "automated" : "manual"}
          </p>
          {e.event_type === "override" && e.old_score !== null && e.new_score !== null && (
            <p className="mt-1 text-meta tabular-nums text-ink-muted">
              {e.old_score.toFixed(2)} → {e.new_score.toFixed(2)}
            </p>
          )}
          {e.note && <p className="mt-1 break-words text-ink">{e.note}</p>}
          {e.event_type === "intervention_action" && (
            <div className="mt-1">
              <span className="text-meta text-ink-muted">
                Outcome: {e.outcome ? OUTCOME_LABELS[e.outcome] : "—"}
              </span>
              {e.outcome === "pending" && <OutcomeEditor orderId={orderId} logId={e.id} />}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
