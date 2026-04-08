"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Zap } from "lucide-react";
import { Link } from "@/i18n/navigation";

export default function SignupPage() {
  const t = useTranslations("auth");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${API_URL}/api/v1/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? t("signup_failed"));
      }
      window.location.href = "/login";
    } catch (err) {
      setError(err instanceof Error ? err.message : t("signup_failed"));
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
          <h1 className="mt-5 text-3xl font-semibold text-text">{t("create_account")}</h1>
          <p className="section-subtitle">{t("start_distributing")}</p>
        </div>

        {error ? <div className="mb-4 rounded-2xl border border-danger/20 bg-danger/10 p-3 text-sm text-danger">{error}</div> : null}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="form-field">
            <label className="form-field__label">{t("name")}</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder={t("name_placeholder")} required className="w-full" />
          </div>
          <div className="form-field">
            <label className="form-field__label">{t("email")}</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("email_placeholder")} required className="w-full" />
          </div>
          <div className="form-field">
            <label className="form-field__label">{t("password")}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("password_placeholder")}
              required
              minLength={8}
              className="w-full"
            />
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? t("creating_account") : t("create_account")}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          {t("already_have_account")}{" "}
          <Link href="/login" className="font-semibold text-accent hover:text-accent-2">
            {t("login")}
          </Link>
        </p>
      </div>
    </div>
  );
}
