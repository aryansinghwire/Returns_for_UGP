export default function ReasonsList({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) {
    return (
      <p className="text-body text-ink-muted">
        No contributing reasons were recorded for this order.
      </p>
    );
  }

  return (
    <ul className="list-disc space-y-1 pl-4 text-body text-ink">
      {/* The key includes the position, because one order can have the same
          reason twice, and using the text alone broke when it did. */}
      {reasons.map((r, i) => (
        <li key={`${i}-${r}`}>{r}</li>
      ))}
    </ul>
  );
}
