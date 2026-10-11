import { useMemo, useState } from "react";
import { useOrders, useScoreHistogram } from "../api/hooks";
import { useAuth } from "../context/AuthContext";
import {
  ORDER_SORTS,
  ORDER_STATUSES,
  type OrderFilters,
  type OrderStatusValue,
} from "../api/types";
import { pluralize } from "../lib/format";
import { enumParam, numberParam, setParam, useUrlState } from "../lib/urlState";
import FilterPanel from "../components/FilterPanel";
import OrdersTable from "../components/OrdersTable";
import RiskDistribution from "../components/RiskDistribution";

const PAGE_SIZE = 25;
const DEFAULT_SORT = "-score";

/**
 * Every filter, the sort order and the page number are kept in the web
 * address.
 *
 * They used to be read from the address once and then kept only inside the
 * page. So a filtered list couldn't be shared, bookmarked, or undone with the
 * Back button - a link one analyst sent showed the next person the whole,
 * unfiltered list.
 *
 * Kept outside the component because useUrlState needs the same function on
 * every render.
 */
function readFilters(params: URLSearchParams): OrderFilters {
  const coldStart = params.get("cold_start");
  return {
    sort: enumParam(params, "sort", ORDER_SORTS) ?? DEFAULT_SORT,
    page: numberParam(params, "page") ?? 1,
    page_size: PAGE_SIZE,
    status: enumParam<OrderStatusValue>(params, "status", ORDER_STATUSES),
    min_score: numberParam(params, "min_score"),
    max_score: numberParam(params, "max_score"),
    country: params.get("country") || undefined,
    product_type: params.get("product_type") || undefined,
    last_n_days: numberParam(params, "last_n_days"),
    cold_start: coldStart === null ? undefined : coldStart === "true",
  };
}

/** Default values are left out of the web address. An untouched list has a
 *  clean address, and only the things you changed show up in it. */
function writeFilters(filters: OrderFilters, params: URLSearchParams): void {
  setParam(params, "sort", filters.sort === DEFAULT_SORT ? undefined : filters.sort);
  setParam(params, "page", filters.page && filters.page > 1 ? filters.page : undefined);
  setParam(params, "status", filters.status);
  setParam(params, "min_score", filters.min_score);
  setParam(params, "max_score", filters.max_score);
  setParam(params, "country", filters.country);
  setParam(params, "product_type", filters.product_type);
  setParam(params, "last_n_days", filters.last_n_days);
  setParam(params, "cold_start", filters.cold_start);
}

/** Sort order and page number change where you are in the list, not which
 *  orders are in it, so they don't count towards the number of filters on. */
const NON_FILTER_KEYS = new Set(["sort", "page", "page_size"]);

export default function QueuePage() {
  const [filters, setFilters] = useUrlState(readFilters, writeFilters);
  const { user } = useAuth();

  const { data, isLoading } = useOrders(filters);
  const { data: histogram, isLoading: histogramLoading } = useScoreHistogram(filters);

  // The score range changes constantly while it's being dragged, but only goes
  // into the web address when the user lets go. So one drag means one update
  // and one request to the server, not one for every pixel.
  const committed = { min: filters.min_score ?? 0, max: filters.max_score ?? 1 };
  const [draft, setDraft] = useState<{ min: number; max: number } | null>(null);
  const window = draft ?? committed;

  function commitWindow() {
    if (!draft) return;
    setFilters(
      (current) => ({
        ...current,
        // A range of 0 to 1 covers every order, so it isn't really a filter.
        // Putting 0 and 1 in the address would make the list look filtered when
        // it isn't.
        min_score: draft.min > 0 ? draft.min : undefined,
        max_score: draft.max < 1 ? draft.max : undefined,
        page: 1,
      }),
      { replace: true },
    );
    setDraft(null);
  }

  const activeFilterCount = useMemo(
    () =>
      Object.entries(filters).filter(
        ([key, value]) => value !== undefined && !NON_FILTER_KEYS.has(key),
      ).length,
    [filters],
  );

  // Only the platform admin can see more than one company. For everyone else,
  // a company column would show the same name on every row.
  const showTenant = user?.role === "admin" && !user?.tenant_slug;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-baseline justify-between gap-3 px-4 pb-2 pt-3">
        <h2 className="text-title font-semibold text-balance">Risk queue</h2>
        {activeFilterCount > 0 && (
          <span className="shrink-0 font-condensed text-meta text-ink-muted">
            {pluralize(activeFilterCount, "filter")} active
          </span>
        )}
      </div>

      <RiskDistribution
        data={histogram}
        isLoading={histogramLoading}
        min={window.min}
        max={window.max}
        onChange={setDraft}
        onCommit={commitWindow}
      />

      <FilterPanel
        filters={filters}
        onChange={setFilters}
        referenceDate={data?.reference_date}
        sinceDate={data?.since_date}
      />

      <OrdersTable
        data={data}
        isLoading={isLoading}
        showTenant={showTenant}
        onPageChange={(page) => setFilters({ ...filters, page })}
      />
    </div>
  );
}
