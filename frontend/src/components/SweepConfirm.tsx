import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useSweepPreview } from "../api/hooks";
import { ACTION_LABELS, type RuleOut } from "../api/types";
import { BUTTON_SECONDARY } from "../lib/controls";
import { formatCount, pluralize } from "../lib/format";

/**
 * The confirmation box in front of "Run rule sweep now".
 *
 * Running the rules changes orders in bulk. One click can record thousands of
 * actions and clear most of the review queue, and there's no undo. So the
 * button first opens a warning that says exactly what will happen, with an
 * up-to-date count for each rule. Nothing runs until a second, deliberate
 * click.
 *
 * It uses a real <dialog> opened with showModal(). An earlier version used a
 * plain div that only claimed to be a dialog: focus stayed on the page behind
 * it, Tab wandered off into that page, and Escape did nothing. This is the one
 * action in the app that can't be undone, so it matters most here.
 */
export default function SweepConfirm({
  rules,
  onConfirm,
  isPending,
}: {
  rules: RuleOut[];
  onConfirm: () => void;
  isPending: boolean;
}) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const activeRules = rules.filter((r) => r.is_active);
  const previews = useSweepPreview(activeRules, open);
  const stillCounting = previews.some((p) => p.isLoading);
  const counts = previews.map((p) => p.data?.total ?? 0);
  const totalActions = counts.reduce((a, b) => a + b, 0);

  // showModal() is what keeps focus inside the box, blocks the page behind it,
  // and makes Escape close it. Just rendering the dialog as open does none of
  // that.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      // Start on Cancel, not on the button that runs the rules, so pressing
      // Enter by accident doesn't run them.
      cancelRef.current?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  function close() {
    setOpen(false);
    openerRef.current?.focus();
  }

  return (
    <>
      <button
        ref={openerRef}
        type="button"
        onClick={() => setOpen(true)}
        disabled={isPending}
        className={BUTTON_SECONDARY}
      >
        {isPending ? "Running…" : "Run rule sweep now"}
      </button>

      <dialog
        ref={dialogRef}
        aria-labelledby="sweep-warning-title"
        onCancel={(e) => {
          // Escape fires `cancel`. Close it through React, so React always knows
          // whether the box is open, rather than letting the browser close it
          // on its own.
          e.preventDefault();
          close();
        }}
        onClick={(e) => {
          // Clicking the dimmed area around the box closes it. The browser reports
          // that click as landing on the dialog itself - but it reports a click on
          // the dialog's own padding the same way. That's why the padding is on the
          // inner wrapper instead. Before, clicking just inside the box's border
          // closed a warning about an action that can't be undone.
          if (e.target === dialogRef.current) close();
        }}
        className="m-auto max-w-xl rounded-[4px] border border-rule-strong bg-panel p-0 text-ink backdrop:bg-black/40"
      >
      {/* Limited in height and scrollable. Otherwise a company with a dozen
          active rules pushes the buttons off the bottom of the screen. */}
      <div className="max-h-[85dvh] overflow-y-auto overscroll-contain p-4">
        <h4 id="sweep-warning-title" className="text-body font-semibold text-balance">
          <span aria-hidden="true">⚠ </span>
          Running a Sweep Acts on the Whole Queue at Once
        </h4>

        {activeRules.length === 0 ? (
          <p className="mt-2 text-body">
            No rules are active, so this sweep would do nothing. Activate a rule first.
          </p>
        ) : (
          <>
            <p className="mt-2 text-body">
              Every <strong>pending</strong> order whose score falls inside an active window will be
              actioned immediately — not queued for review. This is what will happen:
            </p>

            {/* The counts load after the box opens, so read them out to screen readers when they arrive. */}
            <div aria-live="polite" aria-busy={stillCounting}>
              <ul className="mt-2 space-y-1 text-body">
                {activeRules.map((rule, i) => (
                  <li key={rule.id} className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-mono text-meta tabular-nums">
                      {rule.score_min.toFixed(2)}–{rule.score_max.toFixed(2)}
                    </span>
                    <span className="font-medium">{rule.name}</span>
                    <span>
                      → {ACTION_LABELS[rule.action_type]} on{" "}
                      <strong className="tabular-nums">
                        {previews[i]?.isLoading ? "…" : pluralize(counts[i], "pending order")}
                      </strong>
                    </span>
                  </li>
                ))}
              </ul>

              <ul className="mt-3 list-disc space-y-1 pl-5 text-meta">
                <li>
                  <strong className="tabular-nums">
                    {stillCounting ? "…" : pluralize(totalActions, "action")}
                  </strong>{" "}
                  will be written to the audit log, attributed to{" "}
                  <strong>{user?.display_name ?? "you"}</strong>.
                </li>
                <li>
                  Those orders move from <em>pending</em> to <em>actioned</em> and leave the review
                  queue, so an analyst will no longer see them as needing a decision.
                </li>
                <li>
                  <strong>There is no undo.</strong> The dashboard cannot reverse a sweep — the
                  logged actions and the status changes stay until each order is worked
                  individually.
                </li>
                <li>
                  Orders already actioned by the same rule are skipped, so re-running does not
                  duplicate work.
                </li>
              </ul>
            </div>
          </>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              onConfirm();
              close();
            }}
            disabled={isPending || stillCounting || activeRules.length === 0}
            className="rounded-[2px] bg-alarm px-3 py-1.5 text-body font-medium text-paper hover:opacity-85 active:opacity-75 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:opacity-100"
          >
            {isPending
              ? "Running…"
              : stillCounting
                ? "Checking queue…"
                : activeRules.length === 0
                  ? "Run the sweep"
                  : `Yes, Run the Sweep (${formatCount(totalActions)})`}
          </button>
          <button
            ref={cancelRef}
            type="button"
            onClick={close}
            className="rounded-[2px] border border-rule-strong px-3 py-1.5 text-body font-medium text-ink hover:bg-panel"
          >
            Cancel
          </button>
        </div>
      </div>
      </dialog>
    </>
  );
}
