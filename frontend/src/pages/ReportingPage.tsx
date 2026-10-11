/**
 * THIS PAGE IS SWITCHED OFF. Nothing imports this file.
 *
 * /reporting now redirects to /queue (see App.tsx), and the menu link is gone.
 * The import was removed too, so this page isn't in the built website at all -
 * the type checker is the only thing that still reads it.
 *
 * It's kept on purpose. The server's /api/reporting addresses still work and
 * are tested, so turning the page back on just means putting back the import,
 * the route and the menu link. Whether to turn it back on or remove it is
 * still undecided - see section 9 of docs/history/PROJECT_LOG.md. Until then,
 * it's unused on purpose.
 */
import { useId } from "react";
import { useReporting } from "../api/hooks";
import type { CohortType, Granularity } from "../api/types";
import { CONTROL_STACKED, LABEL } from "../lib/controls";
import { formatCount, formatRate, pluralize } from "../lib/format";
import { enumParam, setParam, useUrlState } from "../lib/urlState";
import { useDebouncedDraft } from "../lib/useDebouncedDraft";
import BaselineActualChart from "../components/BaselineActualChart";
import AsyncRegion from "../components/AsyncRegion";

const COUNTRY_BUCKETS = ["Country_A", "Country_B", "Country_C", "Country_D", "Country_E",
 "Country_F", "Country_G", "Country_H", "Country_I"];
const PRODUCT_TYPE_BUCKETS = ["productType_A", "productType_B", "productType_C", "productType_D",
 "productType_E", "productType_F", "productType_G", "productType_H", "productType_I",
 "productType_J", "productType_K"];

const COHORT_TYPES = ["overall", "country", "product_type", "product"] as const;
const GRANULARITIES = ["week", "day"] as const;

interface ReportView {
  cohortType: CohortType;
  cohortKey: string;
  granularity: Granularity;
}

function readView(params: URLSearchParams): ReportView {
  return {
    cohortType: enumParam<CohortType>(params, "cohort_type", COHORT_TYPES) ?? "overall",
    cohortKey: params.get("cohort_key") ?? "",
    granularity: enumParam<Granularity>(params, "granularity", GRANULARITIES) ?? "week",
  };
}

function writeView(view: ReportView, params: URLSearchParams): void {
  setParam(params, "cohort_type", view.cohortType === "overall" ? undefined : view.cohortType);
  setParam(params, "cohort_key", view.cohortKey || undefined);
  setParam(params, "granularity", view.granularity === "week" ? undefined : view.granularity);
}

export default function ReportingPage() {
  const id = useId();
  const [view, setView] = useUrlState(readView, writeView);
  const { cohortType, cohortKey, granularity } = view;

  // Only the typed-in product code needs to wait for the user to stop typing.
  // The other two pickers are dropdowns, which take effect straight away.
  const [refDraft, setRefDraft] = useDebouncedDraft(cohortKey, (next) =>
    // Update from the latest value, so a late save can't bring back a
    // product code the dropdown has cleared in the meantime.
    setView((current) => ({ ...current, cohortKey: next }), { replace: true }),
  );

  const { data, isLoading, error } = useReporting({
    cohort_type: cohortType,
    cohort_key: cohortType === "overall" ? undefined : cohortKey || undefined,
    granularity,
  });

  const buckets = data?.buckets ?? [];
  const totalOrders = buckets.reduce((s, b) => s + b.n_orders, 0);
  const weightedActual = totalOrders
    ? buckets.reduce((s, b) => s + b.actual_return_rate * b.n_orders, 0) / totalOrders
    : 0;
  const baseline = buckets[0]?.baseline_return_rate ?? 0;

  return (
    <div className="space-y-6 p-4">
      <h2 className="text-title font-semibold text-balance text-ink">
        Baseline vs. Actual (Return Rate)
      </h2>
      <p className="max-w-2xl text-meta text-ink-muted">
        &ldquo;Baseline&rdquo; is each cohort&rsquo;s historical return-rate feature (computed
        upstream, before this replay). &ldquo;Actual&rdquo; is the observed outcome rate of these
        historical test orders, bucketed by their (synthetic) order date. This replays past orders
        as a live feed for demonstration — it is not a forecast of future orders.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor={`${id}-cohort`} className={LABEL}>Cohort</label>
          <select
            id={`${id}-cohort`}
            value={cohortType}
            onChange={(e) =>
              setView({ ...view, cohortType: e.target.value as CohortType, cohortKey: "" })
            }
            className={CONTROL_STACKED}
          >
            <option value="overall">Overall</option>
            <option value="country">Country bucket</option>
            <option value="product_type">Product type bucket</option>
            <option value="product">Specific product (ref)</option>
          </select>
        </div>

        {cohortType === "country" && (
          <div>
            <label htmlFor={`${id}-country`} className={LABEL}>Bucket</label>
            <select
              id={`${id}-country`}
              value={cohortKey}
              onChange={(e) => setView({ ...view, cohortKey: e.target.value })}
              className={CONTROL_STACKED}
            >
              <option value="">Select…</option>
              {COUNTRY_BUCKETS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}
        {cohortType === "product_type" && (
          <div>
            <label htmlFor={`${id}-product-type`} className={LABEL}>Bucket</label>
            <select
              id={`${id}-product-type`}
              value={cohortKey}
              onChange={(e) => setView({ ...view, cohortKey: e.target.value })}
              className={CONTROL_STACKED}
            >
              <option value="">Select…</option>
              {PRODUCT_TYPE_BUCKETS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        )}
        {cohortType === "product" && (
          <div>
            <label htmlFor={`${id}-product`} className={LABEL}>Product ref</label>
            <input
              id={`${id}-product`}
              value={refDraft}
              autoComplete="off"
              spellCheck={false}
              onChange={(e) => setRefDraft(e.target.value)}
              placeholder="e.g. 12345678 (see order detail)…"
              className={CONTROL_STACKED}
            />
          </div>
        )}

        <div>
          <label htmlFor={`${id}-granularity`} className={LABEL}>Granularity</label>
          <select
            id={`${id}-granularity`}
            value={granularity}
            onChange={(e) => setView({ ...view, granularity: e.target.value as Granularity })}
            className={CONTROL_STACKED}
          >
            <option value="week">Weekly</option>
            <option value="day">Daily</option>
          </select>
        </div>
      </div>

      <AsyncRegion
        isLoading={isLoading}
        status={
          isLoading
            ? "Loading report"
            : `${pluralize(totalOrders, "order")} across ${pluralize(buckets.length, "period")}`
        }
      >
        {cohortType !== "overall" && !cohortKey ? (
          <p className="text-body text-ink-muted">Select a cohort value above.</p>
        ) : error ? (
          <p role="alert" className="text-body text-alarm">
            Could not load the report: {(error as Error).message}. Reload the page to retry.
          </p>
        ) : isLoading ? (
          <p className="text-body text-ink-muted">Loading report…</p>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap gap-6">
              <KpiTile label="Orders in range" value={formatCount(totalOrders)} />
              <KpiTile label="Weighted actual rate" value={formatRate(weightedActual)} />
              <KpiTile label="Historical baseline" value={formatRate(baseline)} />
            </div>
            <BaselineActualChart buckets={buckets} />
          </div>
        )}
      </AsyncRegion>
    </div>
  );
}

function KpiTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[4px] border border-rule px-4 py-2">
      <p className="text-meta text-ink-muted">{label}</p>
      <p className="text-xl font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
}
