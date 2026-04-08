"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Github, Zap } from "lucide-react";
import { Link } from "@/i18n/navigation";

export default function LoginPage() {
  const t = useTranslations("auth");
  const tc = useTranslations("common");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/callback/credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error("Invalid credentials");
      window.location.href = "/";
    } catch {
      setError(t("invalid_credentials"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="mb-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-accent text-[#20110b] shadow-[0_22px_45px_rgba(255,107,53,0.25)]">
            <Zap size={28} />
          </div>
          <h1 className="mt-5 text-3xl font-semibold text-text">{t("welcome_back")}</h1>
          <p className="section-subtitle">{t("sign_in_to")}</p>
        </div>

        {error ? <div className="mb-4 rounded-2xl border border-danger/20 bg-danger/10 p-3 text-sm text-danger">{error}</div> : null}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="form-field">
            <label className="form-field__label">{t("email")}</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("email_placeholder")} required className="w-full" />
          </div>
          <div className="form-field">
            <label className="form-field__label">{t("password")}</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t("password_placeholder")} required className="w-full" />
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? t("signing_in") : t("login")}
          </button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-border/60" />
          <span className="text-xs uppercase tracking-[0.18em] text-muted">{tc("or_continue_with")}</span>
          <div className="h-px flex-1 bg-border/60" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button className="btn-secondary">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Google
          </button>
          <button className="btn-secondary">
            <Github size={16} />
            GitHub
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-muted">
          {t("dont_have_account")}{" "}
          <Link href="/signup" className="font-semibold text-accent hover:text-accent-2">
            {t("signup")}
          </Link>
        </p>
      </div>
    </div>
  );
}
