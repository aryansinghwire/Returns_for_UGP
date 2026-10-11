import { useId } from "react";
import {
  ORDER_SORTS,
  ORDER_SORT_LABELS,
  ORDER_STATUSES,
  ORDER_STATUS_LABELS,
  PERIOD_OPTIONS,
} from "../api/types";
import type { OrderFilters } from "../api/types";
import type { UrlStateSetter } from "../lib/urlState";
import { BUTTON_SMALL, CONTROL, LABEL } from "../lib/controls";
import { formatDate } from "../lib/format";

// Every country and product-type code in the data. The original data was
// anonymised, so these are just codes, not real countries or categories.
const COUNTRY_BUCKETS = ["Country_A", "Country_B", "Country_C", "Country_D", "Country_E",
  "Country_F", "Country_G", "Country_H", "Country_I"];
const PRODUCT_TYPE_BUCKETS = ["productType_A", "productType_B", "productType_C", "productType_D",
  "productType_E", "productType_F", "productType_G", "productType_H", "productType_I",
  "productType_J", "productType_K"];

interface Props {
  filters: OrderFilters;
  onChange: UrlStateSetter<OrderFilters>;
  /** The date the dashboard treats as "today", sent by the server with the orders. */
  referenceDate?: string | null;
  /** The first day of the date filter that's on, if there is one. */
  sinceDate?: string | null;
}

/**
 * Every filter for the order list except the score range, which moved to the
 * chart above (RiskDistribution). Two boxes asking for a minimum and maximum
 * score didn't show how many orders you were cutting out; the chart does.
 *
 * One row of dropdowns, all the same shape, in the order analysts use them:
 * dates first, then status, then which group of orders.
 */
export default function FilterPanel({ filters, onChange, referenceDate, sinceDate }: Props) {
  const id = useId();

  function set<K extends keyof OrderFilters>(key: K, value: OrderFilters[K]) {
    onChange({ ...filters, [key]: value, page: 1 });
  }

  const field = "flex items-center gap-1.5";

  return (
    <div className="border-b border-rule px-4 py-2">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <div className={field}>
          <label htmlFor={`${id}-period`} className={LABEL}>Period</label>
          <select
            id={`${id}-period`}
            value={filters.last_n_days ?? ""}
            onChange={(e) => set("last_n_days", e.target.value ? Number(e.target.value) : undefined)}
            className={CONTROL}
          >
            {PERIOD_OPTIONS.map((p) => (
              <option key={p.label} value={p.days ?? ""}>{p.label}</option>
            ))}
          </select>
        </div>

        <div className={field}>
          <label htmlFor={`${id}-status`} className={LABEL}>Status</label>
          <select
            id={`${id}-status`}
            value={filters.status ?? ""}
            onChange={(e) => set("status", (e.target.value || undefined) as OrderFilters["status"])}
            className={CONTROL}
          >
            <option value="">Any</option>
            {ORDER_STATUSES.map((s) => (
              <option key={s} value={s}>{ORDER_STATUS_LABELS[s]}</option>
            ))}
          </select>
        </div>

        <div className={field}>
          <label htmlFor={`${id}-country`} className={LABEL}>Country</label>
          <select
            id={`${id}-country`}
            value={filters.country ?? ""}
            onChange={(e) => set("country", e.target.value || undefined)}
            className={CONTROL}
          >
            <option value="">Any</option>
            {COUNTRY_BUCKETS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className={field}>
          <label htmlFor={`${id}-product-type`} className={LABEL}>Type</label>
          <select
            id={`${id}-product-type`}
            value={filters.product_type ?? ""}
            onChange={(e) => set("product_type", e.target.value || undefined)}
            className={CONTROL}
          >
            <option value="">Any</option>
            {PRODUCT_TYPE_BUCKETS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        <div className={field}>
          <label htmlFor={`${id}-cold-start`} className={LABEL}>History</label>
          <select
            id={`${id}-cold-start`}
            value={filters.cold_start === undefined ? "" : String(filters.cold_start)}
            onChange={(e) =>
              set("cold_start", e.target.value === "" ? undefined : e.target.value === "true")
            }
            className={CONTROL}
          >
            <option value="">Any</option>
            <option value="true">Cold-start only</option>
            <option value="false">Warm only</option>
          </select>
        </div>

        <div className={field}>
          <label htmlFor={`${id}-sort`} className={LABEL}>Sort</label>
          <select
            id={`${id}-sort`}
            value={filters.sort ?? "-score"}
            onChange={(e) => set("sort", e.target.value as OrderFilters["sort"])}
            className={CONTROL}
          >
            {ORDER_SORTS.map((s) => (
              <option key={s} value={s}>{ORDER_SORT_LABELS[s]}</option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={() => onChange({ sort: "-score", page: 1, page_size: filters.page_size })}
          className={`${BUTTON_SMALL} ml-auto`}
        >
          Clear filters
        </button>
      </div>

      {/* The period is counted back from the newest order in the data, not
          from today's date. Saying so here stops staff quietly misreading
          which dates they're looking at. */}
      {referenceDate && (
        <p className="mt-2 max-w-[70ch] text-meta text-ink-muted">
          {filters.last_n_days && sinceDate ? (
            <>
              Showing {formatDate(sinceDate)} to {formatDate(referenceDate)}.
            </>
          ) : (
            <>Showing all orders.</>
          )}{" "}
          A period counts back from {formatDate(referenceDate)}, the most recent order date in this
          dataset — these dates are synthesized for the prototype, so there is no real-time window
          to count back from.
        </p>
      )}
    </div>
  );
}
