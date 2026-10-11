import { useId } from "react";
import { useEscalations } from "../api/hooks";
import { LABEL } from "../lib/controls";
import { pluralize } from "../lib/format";
import { setParam, useUrlState } from "../lib/urlState";
import AsyncRegion from "../components/AsyncRegion";
import EscalationsTable from "../components/EscalationsTable";

function readResolved(params: URLSearchParams): boolean {
  // Shows only open escalations unless the address says exactly "true", so
  // resolved ones only appear when someone asks for them.
  return params.get("resolved") === "true";
}

function writeResolved(value: boolean, params: URLSearchParams): void {
  setParam(params, "resolved", value ? true : undefined);
}

export default function EscalationsPage() {
  const id = useId();
  const [showResolved, setShowResolved] = useUrlState(readResolved, writeResolved);
  const { data, isLoading, error } = useEscalations({
    include_resolved: showResolved || undefined,
  });
  const escalations = data ?? [];
  const open = escalations.filter((e) => e.outcome === "pending").length;

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-title font-semibold text-balance text-ink">Escalations</h2>
        <div className="flex items-center gap-2">
          <input
            id={`${id}-resolved`}
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked, { replace: true })}
            className="size-4 accent-current"
          />
          <label htmlFor={`${id}-resolved`} className={`${LABEL} !inline`}>
            Include resolved
          </label>
        </div>
      </div>

      <p className="max-w-2xl text-meta text-ink-muted">
        Orders an Ops Analyst handed up for a decision. An escalation stays open until someone
        records an outcome against it, which is done from the order&rsquo;s own page — the same
        way any other logged intervention is closed out.
      </p>

      <AsyncRegion
        isLoading={isLoading}
        status={
          isLoading
            ? "Loading escalations"
            : error
              ? "Escalations failed to load"
              : showResolved
                ? `${pluralize(escalations.length, "escalation")}, ${open} still open`
                : `${pluralize(open, "open escalation")}`
        }
      >
        {isLoading ? (
          <p className="text-body text-ink-muted">Loading escalations…</p>
        ) : error ? (
          <p role="alert" className="text-body text-alarm">
            Could not load escalations: {(error as Error).message}. Check that the API is
            running, then retry.
          </p>
        ) : (
          <EscalationsTable escalations={escalations} showingResolved={showResolved} />
        )}
      </AsyncRegion>
    </div>
  );
}
