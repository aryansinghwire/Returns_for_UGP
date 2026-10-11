import type { ReactNode } from "react";

/**
 * Wraps an area of the page that loads from the server. Screen readers hear a
 * short status line when it changes; the content itself stays quiet.
 *
 * This exists to stop one mistake: putting `aria-live` on the content.
 * Screen readers read out everything inside an `aria-live` area every time it
 * changes. Wrapped around a 25-row table, that meant all 25 rows were read
 * out again every time a filter changed - with no way to stop it. The rule:
 * only a short status line should be live, never the content.
 *
 * So `aria-busy` marks the area as loading, the one-line summary is the only
 * thing read out, and the table below is read only when the user moves to it.
 */
export default function AsyncRegion({
  isLoading,
  status,
  children,
  className,
}: {
  isLoading?: boolean;
  /** One short line, e.g. "25 orders, page 1 of 4". Read out when it changes. */
  status: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div aria-busy={isLoading} className={className}>
      <p role="status" className="sr-only">
        {status}
      </p>
      {children}
    </div>
  );
}
