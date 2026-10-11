import { Link, useParams } from "react-router-dom";
import { useOrder, useOrderHistory } from "../api/hooks";
import { ORDER_STATUS_LABELS } from "../api/types";
import { LINK } from "../lib/controls";
import { formatDate, formatRate } from "../lib/format";
import ScoreBadge from "../components/ScoreBadge";
import ColdStartBadge from "../components/ColdStartBadge";
import ReasonsList from "../components/ReasonsList";
import OverrideForm from "../components/OverrideForm";
import InterventionActionForm from "../components/InterventionActionForm";
import HistoryTimeline from "../components/HistoryTimeline";

export default function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { data: order, isLoading, error } = useOrder(orderId);
  const { data: history } = useOrderHistory(orderId);

  if (isLoading) return <p className="p-4 text-body text-ink-muted">Loading order…</p>;
  if (error || !order) {
    return (
      <div className="p-4">
        <p role="alert" className="text-body text-alarm">
          {(error as Error)?.message ?? "Order not found."} It may belong to another tenant, or the
          order ID in the URL may be wrong.
        </p>
        <Link to="/queue" className={`text-body ${LINK}`}>
          <span aria-hidden="true">← </span>Back to Queue
        </Link>
      </div>
    );
  }

  const rawEntries = Object.entries(order.raw_features).filter(
    ([, v]) => typeof v !== "object" || v === null,
  );
  const profileEntries = Object.entries(order.raw_features).filter(
    ([, v]) => typeof v === "object" && v !== null,
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4">
      <div>
        <Link to="/queue" className={`text-body ${LINK}`}>
          <span aria-hidden="true">← </span>Back to Queue
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h2
            className="font-mono text-title font-semibold break-all text-ink"
            translate="no"
          >
            {order.order_id}
          </h2>
          <ScoreBadge score={order.current_score} />
          <span className="text-body text-ink-muted">
            {order.tenant} · {formatDate(order.order_date)} ·{" "}
            {ORDER_STATUS_LABELS[order.status] ?? order.status}
          </span>
        </div>
        {order.current_score !== order.model_risk_score && (
          <p className="mt-1 text-meta text-ink-muted">
            Original model score: <span className="tabular-nums">{order.model_risk_score.toFixed(2)}</span>{" "}
            (overridden to <span className="tabular-nums">{order.current_score.toFixed(2)}</span>
            {order.override_reason ? <> — &ldquo;{order.override_reason}&rdquo;</> : null})
          </p>
        )}
        <div className="mt-2">
          <ColdStartBadge customerNoHistory={order.customer_no_history} productNoHistory={order.product_no_history} />
        </div>
      </div>

      <section>
        <h3 className="mb-1 text-body font-semibold text-ink">Contributing reasons</h3>
        <ReasonsList reasons={order.reasons} />
      </section>

      <section className="grid grid-cols-2 gap-4 text-body sm:grid-cols-3">
        <h3 className="sr-only">Model features</h3>
        <Field label="Customer return rate" value={formatRate(order.customer_return_rate)} />
        <Field label="Product return rate" value={formatRate(order.product_return_rate)} />
        <Field label="Avg discount value" value={order.avg_discount_value.toFixed(2)} numeric />
        <Field label="Avg price" value={order.avg_gbp_price.toFixed(2)} numeric />
        <Field label="Country bucket" value={order.country_bucket} />
        <Field label="Product brand bucket" value={order.product_brand_bucket} />
        <Field label="Product type bucket" value={order.product_type_bucket} />
        <Field label="Customer ref" value={order.customer_ref} mono />
        <Field label="Product ref" value={order.product_ref} mono />
      </section>

      {rawEntries.length > 0 && (
        <details className="text-body">
          <summary className="cursor-pointer font-semibold text-ink hover:text-ink">
            Additional Feature Drill-Down
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {rawEntries.map(([k, v]) => (
              <Field key={k} label={k} value={String(v)} />
            ))}
          </div>
          {profileEntries.map(([k, v]) => (
            <div key={k} className="mt-2 min-w-0">
              <p className="text-meta font-medium text-ink-muted">{k}</p>
              <p className="break-all font-mono text-meta text-ink-muted">
                {JSON.stringify(v)}
              </p>
            </div>
          ))}
        </details>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <OverrideForm orderId={order.order_id} currentScore={order.current_score} />
        <InterventionActionForm orderId={order.order_id} />
      </div>

      <section>
        <h3 className="mb-2 text-body font-semibold text-ink">History</h3>
        <HistoryTimeline orderId={order.order_id} entries={history ?? []} />
      </section>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  numeric,
}: {
  label: string;
  value: string;
  mono?: boolean;
  numeric?: boolean;
}) {
  // min-w-0 so a long name gets cut short inside its box, rather than
  // stretching the column.
  return (
    <div className="min-w-0">
      <p className="text-meta text-ink-muted">{label}</p>
      <p
        className={`break-words text-ink  ${
          mono ? "font-mono text-meta" : ""
        } ${mono || numeric ? "tabular-nums" : ""}`}
        translate={mono ? "no" : undefined}
      >
        {value || "—"}
      </p>
    </div>
  );
}
