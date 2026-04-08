"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

export function SiteFooter() {
  const t = useTranslations("footer");

  return (
    <footer className="site-footer">
      <div className="site-footer__grid">
        <div>
          <div className="site-brand">
            <span className="site-brand__mark" aria-hidden="true">
              <span className="site-brand__core" />
              <span className="site-brand__node site-brand__node--top" />
              <span className="site-brand__node site-brand__node--mid" />
              <span className="site-brand__node site-brand__node--bottom" />
            </span>
            <span className="site-brand__text">ContentFlow</span>
          </div>
          <p className="site-footer__copy">
            {t("tagline")}
          </p>
        </div>
        <div className="site-footer__links">
          <Link href="/">{t("home")}</Link>
          <Link href="/docs">{t("docs")}</Link>
          <Link href="/legal/privacy">{t("privacy")}</Link>
          <Link href="/legal/terms">{t("terms")}</Link>
          <a href="#pricing">{t("pricing")}</a>
          <a href="https://github.com/ansdnwls/content-flow">GitHub</a>
        </div>
      </div>
    </footer>
  );
}
