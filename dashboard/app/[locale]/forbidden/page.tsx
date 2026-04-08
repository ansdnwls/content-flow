import Link from "next/link";
import { ShieldAlert } from "lucide-react";

type Props = {
  params: Promise<{ locale: string }>;
};

export default async function ForbiddenPage({ params }: Props) {
  const { locale } = await params;

  return (
    <div className="auth-shell">
      <div className="auth-card text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-warning/15 text-warning">
          <ShieldAlert size={28} />
        </div>
        <h1 className="mt-6 text-4xl font-semibold text-text">This page is not for you.</h1>
        <p className="mt-3 text-sm text-muted">
          You either need the right workspace permissions or a higher plan before this part of ContentFlow opens up.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href={`/${locale}/login`} className="btn-primary">
            Log in
          </Link>
          <Link href={`/${locale}/billing`} className="btn-secondary">
            Upgrade plan
          </Link>
        </div>
      </div>
    </div>
  );
}
