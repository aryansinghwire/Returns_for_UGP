import { useId, useState } from "react";
import { useCreateAction } from "../api/hooks";
import { ACTION_LABELS, ACTION_TYPES, type ActionType } from "../api/types";
import { BUTTON_PRIMARY, CONTROL_STACKED, LABEL } from "../lib/controls";
import { useUnsavedChanges } from "../lib/useUnsavedChanges";

export default function InterventionActionForm({ orderId }: { orderId: string }) {
  const id = useId();
  const [actionType, setActionType] = useState<ActionType>("call_customer");
  const [note, setNote] = useState("");
  const mutation = useCreateAction(orderId);

  useUnsavedChanges(note.trim().length > 0);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(
      { action_type: actionType, note: note || undefined },
      { onSuccess: () => setNote("") },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-[4px] border border-rule p-3">
      <h3 className="text-body font-semibold text-ink">Log an intervention</h3>

      <div>
        <label htmlFor={`${id}-action`} className={LABEL}>Action</label>
        <select
          id={`${id}-action`}
          value={actionType}
          onChange={(e) => setActionType(e.target.value as ActionType)}
          className={`${CONTROL_STACKED} w-full`}
        >
          {ACTION_TYPES.map((a) => (
            <option key={a} value={a}>{ACTION_LABELS[a]}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor={`${id}-note`} className={LABEL}>Note (optional)</label>
        <textarea
          id={`${id}-note`}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          className={`${CONTROL_STACKED} w-full`}
          placeholder="What happened? e.g. Left voicemail, will retry tomorrow…"
        />
      </div>

      <button type="submit" disabled={mutation.isPending} className={BUTTON_PRIMARY}>
        {mutation.isPending ? "Logging…" : "Log action"}
      </button>

      <div aria-live="polite">
        {mutation.isError && (
          <p role="alert" className="text-meta text-alarm">
            Could not log the action: {(mutation.error as Error).message}. Check your connection and
            try again.
          </p>
        )}
        {mutation.isSuccess && !mutation.isPending && (
          <p className="text-meta text-ink-muted">
            Action logged and added to this order&rsquo;s history.
          </p>
        )}
      </div>
    </form>
  );
}
