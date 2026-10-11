import { useId } from "react";
import { Link } from "react-router-dom";
import { useDashboard } from "../api/hooks";
import { ACTION_LABELS, PERIOD_OPTIONS } from "../api/types";
import { formatCount, formatDate, formatRate, pluralize } from "../lib/format";
import { CONTROL, LABEL, LINK } from "../lib/controls";
import { numberParam, setParam, useUrlState } from "../lib/urlState";
import AsyncRegion from "../components/AsyncRegion";
import InfoButton from "../components/InfoButton";
import RiskMixBar from "../components/RiskMixBar";
import StatTile from "../components/StatTile";

/**
 * The home page. Every role lands here first.
 *
 * It has two sections that answer two different questions. They must never
 * look like one table of numbers you can compare:
 *
 *   "Incoming"  — orders, over a period you choose.
 *   "Actions"   — what staff did about them, counted over all time.
 *
 * The period picker only changes the first section, on purpose. The order
 * dates are made up and end on 2021-11-29, but actions are stamped with the
 * real date and time. One "last 7 days" picker for both would put two date
 * ranges years apart under the same label.
 *
 * Three things keep the sections apart: a different background for each, a
 * unit in every label ("orders" or "interventions"), and an "All time" label
 * in the second section where the first one has its period picker. Each
 * section has its own <dl>, and a tile from one never goes in the other.
 */

const PERIOD_DAYS = PERIOD_OPTIONS.map((option) => option.days).filter(
  (days): days is number => days !== undefined,
);

/** Kept outside the component because useUrlState needs the same function on every render. */
function readPeriod(params: URLSearchParams): number | undefined {
  const value = numberParam(params, "last_n_days");
  // Only the periods offered in the picker are accepted. If someone types
  // ?last_n_days=9999 into the address bar, the page falls back to All time
  // instead of the server rejecting the request and the whole page failing.
  return value !== undefined && PERIOD_DAYS.includes(value) ? value : undefined;
}

/** All time is the default, so it's left out of the web address. An untouched
 *  page has a clean address, and only a changed period shows up in it. */
function writePeriod(value: number | undefined, params: URLSearchParams): void {
  setParam(params, "last_n_days", value);
}

export default function DashboardPage() {
  const [lastNDays, setLastNDays] = useUrlState(readPeriod, writePeriod);
  const periodId = useId();

  const { data, isLoading } = useDashboard({ last_n_days: lastNDays });
  const orders = data?.orders;
  const actions = data?.actions;
  const settling = isLoading && !data;

  const ordersStatus = settling
    ? "Loading dashboard"
    : !orders || orders.total === 0
      ? "No orders in the selected period"
      : `${pluralize(orders.total, "order")} in the selected period`;

  const actionsStatus = settling
    ? "Loading dashboard"
    : !actions || actions.total_actions_logged === 0
      ? "No actions logged yet"
      : `${pluralize(actions.open_actions, "intervention")} still open`;

  // The server sends a row for every action type, even ones with no open
  // actions. Drop the zeros here: a list of seven zeros is just noise.
  const openByType = (actions?.open_by_action_type ?? []).filter((row) => row.open_actions > 0);

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="px-6 pb-4 pt-5">
        <h2 className="text-display font-semibold text-balance">Dashboard</h2>
      </div>

      {/* --- what came in: orders, over the chosen period ----------------- */}
      <section aria-labelledby="dash-orders-heading" className="bg-paper px-6 py-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex items-center gap-2">
            <h3 id="dash-orders-heading" className="text-title font-semibold">
              Incoming
            </h3>
            <InfoButton label="About the period these orders are counted over">
              A period counts back from the most recent order date in this dataset, not from
              today — these dates are synthesized for the prototype, so there is no real-time
              window to count back from.
            </InfoButton>
          </div>
          <div>
            <label htmlFor={periodId} className={LABEL}>
              Period
            </label>
            <select
              id={periodId}
              className={`mt-1 ${CONTROL}`}
              value={lastNDays ?? ""}
              onChange={(event) =>
                setLastNDays(event.target.value === "" ? undefined : Number(event.target.value))
              }
            >
              {PERIOD_OPTIONS.map((option) => (
                <option key={option.label} value={option.days ?? ""}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <AsyncRegion isLoading={isLoading} status={ordersStatus} className="mt-5">
          {settling ? (
            <p className="text-head text-ink-muted">Loading dashboard…</p>
          ) : !orders || orders.reference_date === null ? (
            <p className="text-head text-ink-muted">
              No orders have been loaded for this tenant yet.
            </p>
          ) : orders.total === 0 ? (
            <div>
              <p className="text-head text-ink">No orders in this period.</p>
              <p className="mt-2 text-head text-ink-muted">
                Widen the period to see more of the queue.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <dl className="flex flex-wrap gap-x-16 gap-y-6">
                <StatTile label="Orders in" value={orders.total} />
                <StatTile
                  label="Cold-start orders"
                  value={orders.cold_start}
                  hint={`${formatRate(orders.cold_start / orders.total)} of the period`}
                />
              </dl>
              <RiskMixBar mix={orders.risk_mix} total={orders.total} />
            </div>
          )}
        </AsyncRegion>

        {/* Always show the date range the filter used - it's part of the result,
            not extra explanation. Only the note on why the dates are made up
            lives in the heading's info button. */}
        {orders?.reference_date && (
          <p className="mt-5 text-head text-ink-muted">
            {lastNDays && orders.since_date ? (
              <>
                Showing {formatDate(orders.since_date)} to {formatDate(orders.reference_date)}.
              </>
            ) : (
              <>Showing all orders, to {formatDate(orders.reference_date)}.</>
            )}
          </p>
        )}
      </section>

      {/* --- what we did: interventions, over all time -------------------- */}
      <section
        aria-labelledby="dash-actions-heading"
        className="border-y border-rule bg-panel px-6 py-6"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div className="flex items-center gap-2">
            <h3 id="dash-actions-heading" className="text-title font-semibold">
              Actions
            </h3>
            <InfoButton label="About what these intervention counts mean">
              This records that an action was taken, not that it was delivered or answered.
              Calls, SMS, emails and payment conversions leave this system and nothing reports
              back, so every action stays open until someone records an outcome against it.
              These counts are all time; the period above applies only to orders.
            </InfoButton>
          </div>
          {/* In the same spot as the period picker in the section above, for the
              same reason: nobody should have to hunt for which dates a number
              covers. */}
          <span className="font-condensed text-body text-ink-muted">All time</span>
        </div>

        <AsyncRegion isLoading={isLoading} status={actionsStatus} className="mt-5">
          {settling ? (
            <p className="text-head text-ink-muted">Loading dashboard…</p>
          ) : !actions || actions.total_actions_logged === 0 ? (
            <div>
              <p className="text-head text-ink">No actions logged yet.</p>
              <p className="mt-2 max-w-[70ch] text-head text-ink-muted">
                These fill in as your team works the{" "}
                <Link to="/queue" className={LINK}>
                  risk queue
                </Link>{" "}
                — every intervention recorded against an order appears here.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <dl className="flex flex-wrap gap-x-16 gap-y-6">
                <StatTile label="Orders cleared" value={actions.orders_cleared_for_delivery} />
                <StatTile
                  label="Orders flagged for review"
                  value={actions.orders_flagged_for_manual_review}
                />
                <StatTile label="Orders escalated, open" value={actions.orders_escalated_and_open} />
                <StatTile
                  label="Open interventions"
                  value={actions.open_actions}
                  /* Without this, the page can look as if nothing has happened
                     when work has been done that none of the three tiles to the
                     left count - for example, a company whose only action so
                     far was a phone call. */
                  hint={`of ${formatCount(actions.total_actions_logged)} logged all time`}
                />
              </dl>

              <div>
                <h4 className="font-condensed text-body font-medium text-ink-muted">
                  Open interventions by type
                </h4>
                {openByType.length === 0 ? (
                  <p className="mt-3 text-head text-ink-muted">
                    Nothing open — every logged action has an outcome recorded against it.
                  </p>
                ) : (
                  <dl className="mt-3 max-w-xs">
                    {openByType.map((row) => (
                      <div
                        key={row.action_type}
                        className="flex items-baseline justify-between gap-4 border-b border-rule py-2.5 last:border-0"
                      >
                        <dt className="text-head">{ACTION_LABELS[row.action_type]}</dt>
                        <dd className="text-head tabular-nums">{row.open_actions}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            </div>
          )}
        </AsyncRegion>

      </section>
    </div>
  );
}
