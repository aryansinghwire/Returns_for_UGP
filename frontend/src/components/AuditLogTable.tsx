import { useId } from "react";
import { useAuditLog } from "../api/hooks";
import { ACTION_LABELS, ALL_ROLES, ROLE_LABELS, type ActionType, type Role } from "../api/types";
import { BUTTON_SMALL, CONTROL, LABEL } from "../lib/controls";
import { formatCount, formatDateTime, pluralize } from "../lib/format";
import { enumParam, numberParam, setParam, useUrlState } from "../lib/urlState";
import AsyncRegion from "./AsyncRegion";

const EVENT_TYPES = ["override", "intervention_action"] as const;
const EVENT_TYPE_LABELS: Record<(typeof EVENT_TYPES)[number], string> = {
  override: "Overrides",
  intervention_action: "Actions",
};

const PAGE_SIZE = 25;

interface LogView {
  eventType?: (typeof EVENT_TYPES)[number];
  actorRole?: Role;
  page: number;
}

/** The names start with "audit_" because the audit log shares the web address
 *  with anything else on the admin page, so plain "page" could clash. */
function readView(params: URLSearchParams): LogView {
  return {
    eventType: enumParam(params, "log_event", EVENT_TYPES),
    actorRole: enumParam<Role>(params, "log_role", ALL_ROLES),
    page: numberParam(params, "log_page") ?? 1,
  };
}

function writeView(view: LogView, params: URLSearchParams): void {
  setParam(params, "log_event", view.eventType);
  setParam(params, "log_role", view.actorRole);
  setParam(params, "log_page", view.page > 1 ? view.page : undefined);
}

export default function AuditLogTable() {
  const id = useId();
  const [view, setView] = useUrlState(readView, writeView);

  const { data, isLoading, error } = useAuditLog({
    event_type: view.eventType,
    actor_role: view.actorRole,
    page: view.page,
    page_size: PAGE_SIZE,
  });

  // "Not allowed" (403) won't change, and filters can't help, so show only the
  // message. Any other error is probably temporary. Returning early for those
  // too used to remove the filters from the page, leaving no way to change the
  // search and try again without reloading.
  const status = (error as { status?: number } | null)?.status;
  const forbidden = status === 403;

  if (forbidden) {
    return (
      <p role="alert" className="text-body text-alarm">
        {/* This used to name "Ops Manager", a role that no longer exists. It's
            built from ROLE_LABELS now, so it stays correct. */}
        Your current role can&rsquo;t view the audit log (requires{" "}
        {ROLE_LABELS.tenant_admin} or {ROLE_LABELS.admin}).
      </p>
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const entries = data?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <div>
          <label htmlFor={`${id}-event`} className={LABEL}>Event type</label>
          <select
            id={`${id}-event`}
            value={view.eventType ?? ""}
            onChange={(e) =>
              setView({
                ...view,
                eventType: (e.target.value || undefined) as LogView["eventType"],
                page: 1,
              })
            }
            className={`mt-1 ${CONTROL}`}
          >
            <option value="">All event types</option>
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>{EVENT_TYPE_LABELS[t]}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-role`} className={LABEL}>Actor role</label>
          <select
            id={`${id}-role`}
            value={view.actorRole ?? ""}
            onChange={(e) =>
              setView({ ...view, actorRole: (e.target.value || undefined) as Role | undefined, page: 1 })
            }
            className={`mt-1 ${CONTROL}`}
          >
            <option value="">Any actor role</option>
            {ALL_ROLES.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
        </div>
      </div>

      <AsyncRegion
        isLoading={isLoading}
        status={
          isLoading
            ? "Loading audit log"
            : `${pluralize(data?.total ?? 0, "entry", "entries")}, page ${formatCount(view.page)} of ${formatCount(totalPages)}`
        }
      >
        {error ? (
          <p role="alert" className="text-body text-alarm">
            Could not load the audit log: {(error as Error).message}. Adjust the filters above or
            reload to retry.
          </p>
        ) : isLoading ? (
          <p className="text-body text-ink-muted">Loading audit log…</p>
        ) : entries.length === 0 ? (
          <p className="text-body text-ink-muted">
            No audit entries match these filters. Clear them to see the full log.
          </p>
        ) : (
          <>
            <table className="w-full border-collapse text-body">
              <caption className="sr-only">
                Overrides and interventions, page {view.page} of {totalPages}
              </caption>
              <thead className="text-left text-meta uppercase tracking-wide text-ink-muted">
                <tr>
                  <th scope="col" className="px-2 py-1 font-medium">When</th>
                  <th scope="col" className="px-2 py-1 font-medium">Order</th>
                  <th scope="col" className="px-2 py-1 font-medium">Tenant</th>
                  <th scope="col" className="px-2 py-1 font-medium">Event</th>
                  <th scope="col" className="px-2 py-1 font-medium">Actor</th>
                  <th scope="col" className="px-2 py-1 font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id} className="border-t border-rule">
                    <td className="px-2 py-1.5 text-meta tabular-nums text-ink-muted">
                      <time dateTime={e.created_at}>{formatDateTime(e.created_at)}</time>
                    </td>
                    <th scope="row" className="px-2 py-1.5 text-left font-mono text-meta font-normal" translate="no">
                      {e.order_id}
                    </th>
                    <td className="px-2 py-1.5">{e.tenant}</td>
                    <td className="px-2 py-1.5">
                      {e.event_type === "override"
                        ? "Override"
                        : (ACTION_LABELS[e.action_type as ActionType] ?? e.action_type ?? "Action")}
                    </td>
                    <td className="px-2 py-1.5 text-meta">
                      {e.actor_name || ROLE_LABELS[e.actor_role]} ({ROLE_LABELS[e.actor_role]})
                    </td>
                    <td
                      className="max-w-xs truncate px-2 py-1.5 text-meta text-ink-muted"
                      title={e.note ?? undefined}
                    >
                      {e.note || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <nav
              aria-label="Audit log pagination"
              className="mt-3 flex items-center justify-between gap-3 text-body"
            >
              <span className="tabular-nums text-ink-muted">
                {pluralize(data?.total ?? 0, "entry", "entries")} — page {formatCount(view.page)} of{" "}
                {formatCount(totalPages)}
              </span>
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  disabled={view.page <= 1}
                  onClick={() => setView({ ...view, page: view.page - 1 })}
                  className={BUTTON_SMALL}
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={view.page >= totalPages}
                  onClick={() => setView({ ...view, page: view.page + 1 })}
                  className={BUTTON_SMALL}
                >
                  Next
                </button>
              </div>
            </nav>
          </>
        )}
      </AsyncRegion>
    </div>
  );
}
