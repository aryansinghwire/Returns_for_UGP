/**
 * Lets staff replace an order's risk score by hand. The new score goes in
 * order_status, never on the order itself. The model's own score never
 * changes, so it can always be checked, and the override is recorded in
 * intervention_log.
 */
import { useId, useRef, useState } from "react";
import { useOverrideOrder } from "../api/hooks";
import { BUTTON_PRIMARY, CONTROL_STACKED, LABEL } from "../lib/controls";
import { useUnsavedChanges } from "../lib/useUnsavedChanges";

export default function OverrideForm({ orderId, currentScore }: { orderId: string; currentScore: number }) {
  const id = useId();
  const [newScore, setNewScore] = useState(currentScore);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const mutation = useOverrideOrder(orderId);

  // A half-written reason is the one thing on this page worth warning about before leaving.
  useUnsavedChanges(reason.trim().length > 0);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // The button stays clickable and checks the form here, rather than being
    // greyed out - a greyed-out button doesn't say what's wrong.
    if (!reason.trim()) {
      setReasonError("Give a reason for the override — it is recorded in the audit log.");
      reasonRef.current?.focus();
      return;
    }
    setReasonError(null);
    mutation.mutate({ new_score: newScore, reason }, { onSuccess: () => setReason("") });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3 rounded-[4px] border border-rule p-3">
      <h3 className="text-body font-semibold text-ink">Override score</h3>

      <div>
        <label htmlFor={`${id}-score`} className={LABEL}>
          New Score: <span className="tabular-nums">{newScore.toFixed(2)}</span>
        </label>
        <input
          id={`${id}-score`}
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={newScore}
          onChange={(e) => setNewScore(Number(e.target.value))}
          className="mt-1 w-full"
        />
      </div>

      <div>
        <label htmlFor={`${id}-reason`} className={LABEL}>Reason (required)</label>
        <textarea
          id={`${id}-reason`}
          ref={reasonRef}
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
            if (reasonError) setReasonError(null);
          }}
          rows={2}
          aria-invalid={reasonError ? true : undefined}
          aria-describedby={reasonError ? `${id}-reason-error` : undefined}
          className={`${CONTROL_STACKED} w-full`}
          placeholder="Why are you overriding the model’s score? e.g. Customer called to confirm the address…"
        />
        {reasonError && (
          <p id={`${id}-reason-error`} role="alert" className="mt-1 text-meta text-alarm">
            {reasonError}
          </p>
        )}
      </div>

      <button type="submit" disabled={mutation.isPending} className={BUTTON_PRIMARY}>
        {mutation.isPending ? "Saving…" : "Apply override"}
      </button>

      <div aria-live="polite">
        {mutation.isError && (
          <p role="alert" className="text-meta text-alarm">
            Could not save the override: {(mutation.error as Error).message}. Check your connection
            and try again.
          </p>
        )}
        {mutation.isSuccess && !mutation.isPending && (
          <p className="text-meta text-ink-muted">
            Override applied and written to the audit log.
          </p>
        )}
      </div>
    </form>
  );
}
