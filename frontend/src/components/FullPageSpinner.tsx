export default function FullPageSpinner() {
  return (
    <div className="flex h-screen items-center justify-center bg-paper">
      <p role="status" className="text-body text-ink-muted">
        Loading…
      </p>
    </div>
  );
}
