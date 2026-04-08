import Link from "next/link";
import { Wrench } from "lucide-react";

type Props = {
  params: Promise<{ locale: string }>;
};

export default async function MaintenancePage({ params }: Props) {
  const { locale } = await params;

  return (
    <div className="auth-shell">
      <div className="auth-card text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-accent/15 text-accent">
          <Wrench size={28} />
        </div>
        <h1 className="mt-6 text-4xl font-semibold text-text">We&apos;re paused for maintenance.</h1>
        <p className="mt-3 text-sm text-muted">
          The platform is temporarily paused while we tighten the rails. Expected return window: under 30 minutes.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href={`/${locale}`} className="btn-primary">
            Back to dashboard
          </Link>
          <a href="https://status.contentflow.dev" className="btn-secondary">
            Status page
          </a>
        </div>
      </div>
    </div>
  );
}
