import { formatCount } from "../lib/format";

/**
 * One number and its label, as a <dt>/<dd> pair.
 *
 * Moved out of RiskDistribution, which had the same markup written in. The
 * dashboard has seven of these, and copying styles around is how the main
 * button once lost its hover effect in six places.
 *
 * A dash means only "the number hasn't loaded yet". Once it has loaded, an
 * empty tile shows `0`, never `—`. They mean different things, and mixing them
 * up makes an empty page look broken.
 */
export default function StatTile({
  label,
  value,
  hint,
  isLoading = false,
}: {
  label: string;
  value: number;
  /** A second line under the number, e.g. a percentage or a short note. */
  hint?: string;
  isLoading?: boolean;
}) {
  return (
    <div>
      <dt className="font-condensed text-body font-medium text-ink-muted">{label}</dt>
      <dd className="text-display tabular-nums">{isLoading ? "—" : formatCount(value)}</dd>
      {hint && <dd className="text-body text-ink-muted">{hint}</dd>}
    </div>
  );
}
