import { useId } from "react";
import { useAlerts } from "../api/hooks";
import { CONTROL_STACKED, LABEL } from "../lib/controls";
import { pluralize } from "../lib/format";
import { useDebouncedDraft } from "../lib/useDebouncedDraft";
import { numberParam, setParam, useUrlState } from "../lib/urlState";
import AlertsTable from "../components/AlertsTable";
import AsyncRegion from "../components/AsyncRegion";

const DEFAULT_MIN_GAP = 0.15;

function readMinGap(params: URLSearchParams): number {
  const value = numberParam(params, "min_gap");
  // Someone editing the web address by hand mustn't be able to set the
  // threshold outside 0 to 1, which would quietly empty the table.
  return value !== undefined && value >= 0 && value <= 1 ? value : DEFAULT_MIN_GAP;
}

function writeMinGap(value: number, params: URLSearchParams): void {
  setParam(params, "min_gap", value === DEFAULT_MIN_GAP ? undefined : value);
}

export default function AlertsPage() {
  const id = useId();
  const [minGap, setMinGap] = useUrlState(readMinGap, writeMinGap);

  // This value is typed in, not picked. Each key press is held here, and only
  // goes into the web address once typing stops - replacing the current
  // history entry rather than adding one. Before, typing "0.25" sent four
  // requests to the server and took four presses of Back to undo.
  const [draftGap, setDraftGap] = useDebouncedDraft(minGap, (next) =>
    setMinGap(next, { replace: true }),
  );

  const { data, isLoading, error } = useAlerts({ min_gap: minGap });
  const alerts = data ?? [];

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-title font-semibold text-balance text-ink">
          Spike Alerts
        </h2>
        <div>
          <label htmlFor={`${id}-min-gap`} className={LABEL}>
            Min Gap
          </label>
          <input
            id={`${id}-min-gap`}
            type="number"
            inputMode="decimal"
            autoComplete="off"
            min={0}
            max={1}
            step={0.05}
            value={draftGap}
            onChange={(e) => {
              const next = Number(e.target.value);
              if (Number.isFinite(next)) setDraftGap(Math.min(1, Math.max(0, next)));
            }}
            className={`${CONTROL_STACKED} w-24 tabular-nums`}
          />
        </div>
      </div>

      <p className="max-w-2xl text-meta text-ink-muted">
        Compares each cohort&rsquo;s return rate over the last 14 days of (synthetic) order
        dates against its historical baseline. Cohorts with fewer than the minimum sample size are
        skipped to avoid noise from small groups.
      </p>

      {/* Always on the page, not only once results arrive. Screen readers
          only announce changes to it, so if it appeared at the same time as
          its text, nothing would be read out. */}
      <AsyncRegion
        isLoading={isLoading}
        status={
          isLoading
            ? "Loading alerts"
            : error
              ? "Alerts failed to load"
              : `${pluralize(alerts.length, "spike alert")} at this threshold`
        }
      >
        {isLoading ? (
          <p className="text-body text-ink-muted">Loading alerts…</p>
        ) : error ? (
          <p role="alert" className="text-body text-alarm">
            Could not load alerts: {(error as Error).message}. Check that the API is running, then
            retry.
          </p>
        ) : (
          <AlertsTable alerts={alerts} />
        )}
      </AsyncRegion>
    </div>
  );
}
