import { Link } from "react-router-dom";
import { LINK } from "../lib/controls";

export default function NotFoundPage() {
  return (
    <div className="p-4">
      <h2 className="text-title font-semibold text-balance text-ink">
        Page Not Found
      </h2>
      <p className="mt-1 text-body text-ink-muted">
        That URL does not match anything in this dashboard.{" "}
        <Link to="/queue" className={LINK}>
          Back to the Risk Queue
        </Link>
        .
      </p>
    </div>
  );
}
