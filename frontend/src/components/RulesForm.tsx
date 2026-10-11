import { useId, useRef, useState } from "react";
import { useApp } from "../context/AppContext";
import { useAuth } from "../context/AuthContext";
import { useCreateRule, useEvaluateRules, useRules, useUpdateRule } from "../api/hooks";
import { ACTION_LABELS, RULE_ACTION_TYPES, type ActionType, type RuleOut } from "../api/types";
import { BUTTON_PRIMARY, CONTROL_STACKED, LABEL } from "../lib/controls";
import { pluralize } from "../lib/format";
import ScoreRangeSlider from "./ScoreRangeSlider";
import SweepConfirm from "./SweepConfirm";

/** Lets you change an existing rule's score range in place. The range is kept
 *  here while dragging, and only saved when you let go - otherwise every
 *  pixel of a drag would send a request. */
function RuleWindowCell({ rule, canEdit }: { rule: RuleOut; canEdit: boolean }) {
  const updateRule = useUpdateRule();
  const [draft, setDraft] = useState<{ min: number; max: number } | null>(null);
  const window = draft ?? { min: rule.score_min, max: rule.score_max };

  function commit() {
    if (!draft) return;
    if (draft.min === rule.score_min && draft.max === rule.score_max) {
      setDraft(null);
      return;
    }
    updateRule.mutate(
      { ruleId: rule.id, body: { score_min: draft.min, score_max: draft.max } },
      { onSettled: () => setDraft(null) },
    );
  }

  if (!canEdit) {
    return (
      <span className="font-mono text-meta tabular-nums">
        {rule.score_min.toFixed(2)} – {rule.score_max.toFixed(2)}
      </span>
    );
  }

  // The slider itself decides when a drag or key press has finished - it's the
  // only thing that can see the mouse let go outside it, or an arrow key
  // released. This used to be a <div> around it with its own mouse and keyboard
  // handlers, which missed any release outside the div.
  return (
    <ScoreRangeSlider
      label={`Applies to scores, ${rule.name}`}
      min={window.min}
      max={window.max}
      disabled={updateRule.isPending}
      onChange={setDraft}
      onCommit={commit}
    />
  );
}

export default function RulesForm() {
  const id = useId();
  const { tenant } = useApp();
  const { user } = useAuth();
  const { data: rules, isLoading } = useRules();
  const createRule = useCreateRule();
  const updateRule = useUpdateRule();
  const evaluateRules = useEvaluateRules();

  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const [window, setWindow] = useState({ min: 0.75, max: 1.0 });
  const [actionType, setActionType] = useState<ActionType>("flag_for_manual_review");

  // AppContext has already worked this out. For anyone who belongs to a
  // company, it's always their company, so only the platform admin can see
  // the "choose a company" message below.
  const targetTenant = tenant;

  if (!targetTenant) {
    return (
      <p className="text-body text-ink-muted">
        Select a specific tenant (top-left) to view and manage its score windows — rules belong
        to one tenant at a time.
      </p>
    );
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setNameError("Name the rule so it can be told apart in the audit log.");
      nameRef.current?.focus();
      return;
    }
    setNameError(null);
    createRule.mutate(
      { name, score_min: window.min, score_max: window.max, action_type: actionType },
      { onSuccess: () => setName("") },
    );
  }

  const visible = rules ?? [];

  return (
    <div className="space-y-4">
      <form
        onSubmit={submit}
        noValidate
        className="flex flex-wrap items-end gap-x-6 gap-y-4 rounded-[4px] border border-rule p-3"
      >
        <div>
          <label htmlFor={`${id}-name`} className={LABEL}>Rule name</label>
          <input
            id={`${id}-name`}
            ref={nameRef}
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (nameError) setNameError(null);
            }}
            autoComplete="off"
            aria-invalid={nameError ? true : undefined}
            aria-describedby={nameError ? `${id}-name-error` : undefined}
            placeholder="e.g. High-risk auto-flag…"
            className={CONTROL_STACKED}
          />
          {nameError && (
            <p id={`${id}-name-error`} role="alert" className="mt-1 text-meta text-alarm">
              {nameError}
            </p>
          )}
        </div>

        <ScoreRangeSlider label="Applies to scores" min={window.min} max={window.max} onChange={setWindow} />

        <div>
          <label htmlFor={`${id}-action`} className={LABEL}>Action</label>
          <select
            id={`${id}-action`}
            value={actionType}
            onChange={(e) => setActionType(e.target.value as ActionType)}
            className={CONTROL_STACKED}
          >
            {RULE_ACTION_TYPES.map((a) => (
              <option key={a} value={a}>{ACTION_LABELS[a]}</option>
            ))}
          </select>
        </div>

        <button type="submit" disabled={createRule.isPending} className={BUTTON_PRIMARY}>
          {createRule.isPending ? "Adding…" : "Add rule"}
        </button>
      </form>

      <p className="text-meta text-ink-muted">
        A rule fires on orders whose current score falls <em>inside</em> the window, so a tenant can send a
        cheap reminder in the 0.50–0.75 band and reserve a phone call for 0.90–1.00 without the two overlapping.
      </p>

      <SweepConfirm
        rules={rules ?? []}
        onConfirm={() => evaluateRules.mutate()}
        isPending={evaluateRules.isPending}
      />

      <div aria-live="polite">
        {(createRule.error || updateRule.error) && (
          <p role="alert" className="text-body text-alarm">
            Could not save the rule: {(createRule.error ?? updateRule.error)?.message}. Check the
            window bounds and try again.
          </p>
        )}

        {evaluateRules.data && (
          <p className="text-body text-ink-muted">
            Sweep complete: {pluralize(evaluateRules.data.rules_evaluated, "active rule")} evaluated,{" "}
            {pluralize(evaluateRules.data.actions_created, "new automated action")} created.
          </p>
        )}
      </div>

      {isLoading ? (
        <p className="text-body text-ink-muted">Loading rules…</p>
      ) : visible.length === 0 ? (
        <p className="text-body text-ink-muted">
          No score windows configured for this tenant yet.
        </p>
      ) : (
        <table className="w-full border-collapse text-body">
          <caption className="sr-only">Automated score windows for this tenant</caption>
          <thead className="text-left text-meta uppercase tracking-wide text-ink-muted">
            <tr>
              <th scope="col" className="px-2 py-1 font-medium">Name</th>
              <th scope="col" className="px-2 py-1 font-medium">Applies to scores</th>
              <th scope="col" className="px-2 py-1 font-medium">Action</th>
              <th scope="col" className="px-2 py-1 font-medium">Active</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.id} className="border-t border-rule align-top">
                <th scope="row" className="px-2 py-3 text-left font-normal">
                  {r.name}
                  <span className="block text-meta text-ink-muted">{r.tenant}</span>
                </th>
                <td className="px-2 py-3">
                  <RuleWindowCell rule={r} canEdit={user?.role === "admin" || r.tenant_slug === user?.tenant_slug} />
                </td>
                <td className="px-2 py-3">{ACTION_LABELS[r.action_type]}</td>
                <td className="px-2 py-3">
                  <button
                    type="button"
                    aria-pressed={r.is_active}
                    aria-label={`${r.name}: ${r.is_active ? "active" : "inactive"}. Activate or deactivate.`}
                    onClick={() => updateRule.mutate({ ruleId: r.id, body: { is_active: !r.is_active } })}
                    disabled={updateRule.isPending}
                    /* Filled in when on, outlined when off. It used to be
                       green for on and grey for off, but in this app colour
                       only means risk. aria-pressed tells screen readers
                       whether it's on. */
                    className={`rounded-[2px] px-2 py-0.5 font-condensed text-meta font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${
                      r.is_active
                        ? "bg-ink text-paper hover:opacity-85"
                        : "border border-rule text-ink-muted hover:bg-panel"
                    }`}
                  >
                    {r.is_active ? "Active" : "Inactive"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
