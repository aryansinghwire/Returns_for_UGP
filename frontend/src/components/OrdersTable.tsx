import { Link } from "react-router-dom";
import { ORDER_STATUS_LABELS, type PaginatedOrders } from "../api/types";
import { BUTTON_SMALL, LINK, TH } from "../lib/controls";
import { formatCount, formatDate, pluralize } from "../lib/format";
import ScoreBadge from "./ScoreBadge";
import ColdStartBadge from "./ColdStartBadge";

interface Props {
  data: PaginatedOrders | undefined;
  isLoading: boolean;
  onPageChange: (page: number) => void;
  /** Hidden when every row would show the same company. */
  showTenant: boolean;
}

export default function OrdersTable({ data, isLoading, onPageChange, showTenant }: Props) {
  if (isLoading && !data) {
    return <p className="p-4 text-body text-ink-muted">Loading orders…</p>;
  }
  if (!data || data.items.length === 0) {
    return (
      <div className="p-4">
        <p className="text-body text-ink">No orders match these filters.</p>
        <p className="mt-1 text-body text-ink-muted">
          Widen the score window or clear a filter to see more of the queue.
        </p>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 overflow-auto">
        {/* table-fixed, so long reasons really are cut short. With the default
            layout, a cell grows to fit its text whatever line-clamp says, so
            one long reason made the whole table too wide and it scrolled
            sideways - the opposite of what cutting it short was for. */}
        <table className="w-full table-fixed border-collapse text-body">
          <caption className="sr-only">
            Orders ranked by return risk, page {data.page} of {totalPages}
          </caption>
          <thead className="sticky top-0 z-10 bg-panel text-left">
            <tr className="border-b border-rule">
              {/* A fixed layout needs each column's width set. The reason column
                  is the only one left without a width, so it gets the rest. */}
              <th scope="col" className={`${TH} w-28 px-4 py-1.5`}>Score</th>
              <th scope="col" className={`${TH} w-44 px-3 py-1.5`}>Order</th>
              {showTenant && <th scope="col" className={`${TH} w-36 px-3 py-1.5`}>Tenant</th>}
              <th scope="col" className={`${TH} w-28 px-3 py-1.5`}>Date</th>
              <th scope="col" className={`${TH} w-24 px-3 py-1.5`}>Status</th>
              {/* The reason is what tells staff whether to act, so it gets all the
                  spare width. It used to be cut short while a company column
                  showed the same name on every row. */}
              <th scope="col" className={`${TH} px-3 py-1.5`}>Top reason</th>
              <th scope="col" className={`${TH} w-44 px-3 py-1.5`}>Flags</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((o) => (
              <tr
                key={o.order_id}
                /* Otherwise, when keyboard focus scrolls to a row, the header
                   that stays on screen would cover it. */
                className="scroll-mt-8 border-b border-rule/60 hover:bg-panel"
              >
                <td className="px-4 py-1.5">
                  <ScoreBadge score={o.current_score} size="sm" />
                </td>
                <th scope="row" className="px-3 py-1.5 text-left font-normal">
                  <Link
                    to={`/orders/${o.order_id}`}
                    className={`block truncate font-mono text-meta ${LINK}`}
                    translate="no"
                  >
                    {o.order_id}
                  </Link>
                </th>
                {showTenant && <td className="truncate px-3 py-1.5" title={o.tenant}>{o.tenant}</td>}
                <td className="whitespace-nowrap px-3 py-1.5 tabular-nums text-ink-muted">
                  {formatDate(o.order_date)}
                </td>
                <td className="whitespace-nowrap px-3 py-1.5 text-ink-muted">
                  {ORDER_STATUS_LABELS[o.status] ?? o.status}
                </td>
                {/* Some orders have no reasons, when nothing about them stood
                    out. A dash is clearer than an empty cell. */}
                <td className="px-3 py-1.5 text-ink-muted" title={o.reasons[0] ?? undefined}>
                  <span className="line-clamp-1">{o.reasons[0] ?? "—"}</span>
                </td>
                <td className="px-3 py-1.5">
                  <ColdStartBadge
                    customerNoHistory={o.customer_no_history}
                    productNoHistory={o.product_no_history}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <nav
        aria-label="Order queue pagination"
        className="flex items-center justify-between gap-3 border-t border-rule px-4 py-2"
      >
        {/* Only this one short line is read out to screen readers when a
            filter changes - not the whole table. See AsyncRegion for why. */}
        <span role="status" className="tabular-nums text-ink-muted">
          {pluralize(data.total, "order")} — page {formatCount(data.page)} of{" "}
          {formatCount(totalPages)}
        </span>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            disabled={data.page <= 1}
            onClick={() => onPageChange(data.page - 1)}
            className={BUTTON_SMALL}
          >
            Previous
          </button>
          <button
            type="button"
            disabled={data.page >= totalPages}
            onClick={() => onPageChange(data.page + 1)}
            className={BUTTON_SMALL}
          >
            Next
          </button>
        </div>
      </nav>
    </div>
  );
}
