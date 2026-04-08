"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Link } from "@/i18n/navigation";

function VerifyEmailContent() {
  const t = useTranslations("auth");
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading"
  );

  useEffect(() => {
    if (!token) {
      setStatus("error");
      return;
    }

    const API_URL =
      process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${API_URL}/api/v1/auth/verify-email/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((res) => {
        setStatus(res.ok ? "success" : "error");
      })
      .catch(() => setStatus("error"));
  }, [token]);

  return (
    <div className="glass-card p-8 max-w-md w-full text-center">
      {status === "loading" && (
        <>
          <Loader2 size={48} className="text-accent animate-spin mx-auto" />
          <h2 className="text-xl font-bold mt-4">{t("verifying_email")}</h2>
        </>
      )}
      {status === "success" && (
        <>
          <CheckCircle size={48} className="text-success mx-auto" />
          <h2 className="text-xl font-bold mt-4">{t("email_verified")}</h2>
          <p className="text-muted mt-2">{t("email_verified_desc")}</p>
          <Link href="/" className="btn-primary inline-block mt-4">
            {t("go_to_dashboard")}
          </Link>
        </>
      )}
      {status === "error" && (
        <>
          <XCircle size={48} className="text-danger mx-auto" />
          <h2 className="text-xl font-bold mt-4">{t("verification_failed")}</h2>
          <p className="text-muted mt-2">{t("verification_failed_desc")}</p>
          <Link href="/login" className="btn-primary inline-block mt-4">
            {t("back_to_login")}
          </Link>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  const t = useTranslations("auth");
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <Suspense
        fallback={
          <div className="glass-card p-8 max-w-md w-full text-center">
            <Loader2 size={48} className="text-accent animate-spin mx-auto" />
            <h2 className="text-xl font-bold mt-4">{t("loading_text")}</h2>
          </div>
        }
      >
        <VerifyEmailContent />
      </Suspense>
    </div>
  );
}
