"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { ThemeToggle } from "@/components/theme-toggle";

export function SiteHeader() {
  const t = useTranslations("nav");

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="site-brand" href="/">
          <span className="site-brand__mark" aria-hidden="true">
            <span className="site-brand__core" />
            <span className="site-brand__node site-brand__node--top" />
            <span className="site-brand__node site-brand__node--mid" />
            <span className="site-brand__node site-brand__node--bottom" />
          </span>
          <span className="site-brand__text">ContentFlow</span>
        </Link>
        <nav className="site-nav" aria-label="Primary">
          <Link className="site-nav__link" href="/#platforms">
            {t("platforms")}
          </Link>
          <Link className="site-nav__link" href="/#features">
            {t("signal")}
          </Link>
          <Link className="site-nav__link" href="/#pricing">
            {t("pricing")}
          </Link>
          <Link className="site-nav__link" href="/docs">
            {t("docs")}
          </Link>
        </nav>
        <div className="site-header__actions">
          <ThemeToggle />
          <Link className="button button--ghost" href="/docs">
            {t("api_docs")}
          </Link>
          <a className="button button--primary" href="#pricing">
            {t("start_free")}
          </a>
        </div>
      </div>
    </header>
  );
}
