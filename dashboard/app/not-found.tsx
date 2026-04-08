import Link from "next/link";

export default function NotFoundPage() {
  return (
    <div className="auth-shell">
      <div className="auth-card text-center">
        <div className="pill mx-auto">404</div>
        <h1 className="mt-6 text-5xl font-semibold text-text">This page isn&apos;t on any of the 21 platforms either.</h1>
        <p className="mt-3 text-sm text-muted">
          The route you asked for does not exist. Head back home or return to the previous page and try a different path.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/en" className="btn-primary">
            Home
          </Link>
          <Link href="/en/posts" className="btn-secondary">
            Open posts
          </Link>
        </div>
      </div>
    </div>
  );
}
