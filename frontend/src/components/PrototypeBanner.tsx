import { useState } from "react";
import { useMeta } from "../api/hooks";
import { sessionGet, sessionSet } from "../lib/storage";

const DISMISS_KEY = "returns-dashboard.banner-dismissed";

/**
 * Black, white and grey, like everything that isn't about risk. It used to
 * be a wide amber block above the order list - the most eye-catching thing on
 * the page, for a notice you only need to read once. A thin line and a short
 * label are enough.
 */
export default function PrototypeBanner() {
  const { data: meta } = useMeta();
  // Read through the safe helper. A browser set to block site storage throws
  // an error when it's read, and doing that here once crashed the whole page.
  const [dismissed, setDismissed] = useState(() => sessionGet(DISMISS_KEY) === "1");

  if (dismissed || !meta) return null;

  return (
    <div className="flex items-baseline gap-3 border-b border-rule bg-panel px-4 py-1.5">
      <span className="shrink-0 font-condensed text-meta font-semibold text-ink">
        Prototype
      </span>
      <p className="min-w-0 flex-1 text-meta text-ink-muted">{meta.notice}</p>
      <button
        type="button"
        onClick={() => {
          sessionSet(DISMISS_KEY, "1");
          setDismissed(true);
        }}
        className="shrink-0 rounded-[2px] px-1 text-ink-muted hover:bg-rule hover:text-ink"
        aria-label="Dismiss prototype notice"
      >
        <span aria-hidden="true">✕</span>
      </button>
    </div>
  );
}
