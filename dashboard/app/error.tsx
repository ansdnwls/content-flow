"use client";

import Link from "next/link";
import { AlertTriangle, RefreshCcw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="auth-shell">
      <div className="auth-card text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-danger/15 text-danger">
          <AlertTriangle size={28} />
        </div>
        <h1 className="mt-6 text-4xl font-semibold text-text">Something broke mid-burst.</h1>
        <p className="mt-3 text-sm text-muted">
          The system hit an unexpected issue. Try again, or head back to a stable page while the pipeline recovers.
        </p>
        <p className="mt-2 text-xs text-muted">{error.digest ? `Reference: ${error.digest}` : "Reference unavailable"}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <button type="button" className="btn-primary" onClick={reset}>
            <RefreshCcw size={16} /> Try again
          </button>
          <Link href="/en" className="btn-secondary">
            Back to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
