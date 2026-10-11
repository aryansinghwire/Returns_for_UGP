/**
 * "New customer" and "New product" labels - for orders where the model has no
 * past orders from that customer, or for that product. Grey only.
 *
 * They used to be light blue and purple, right next to the risk score - two
 * extra colours competing with the only thing that should be coloured. A thin
 * border and grey text are enough to say "side note".
 */
export default function ColdStartBadge({
  customerNoHistory,
  productNoHistory,
}: {
  customerNoHistory: boolean;
  productNoHistory: boolean;
}) {
  if (!customerNoHistory && !productNoHistory) return null;

  const chip =
    "rounded-[2px] border border-rule px-1.5 py-px font-condensed text-meta text-ink-muted";

  return (
    <div className="flex flex-wrap gap-1">
      {customerNoHistory && <span className={chip}>New customer</span>}
      {productNoHistory && <span className={chip}>New product</span>}
    </div>
  );
}
