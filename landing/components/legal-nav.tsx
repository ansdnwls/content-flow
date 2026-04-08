"use client";

import { usePathname } from "@/i18n/navigation";
import { Link } from "@/i18n/navigation";
import { legalNavigation } from "@/lib/legal-content";

export function LegalNav() {
  const pathname = usePathname();

  return (
    <nav className="legal-sidebar" aria-label="Legal pages">
      <div className="legal-sidebar__section">
        <span className="eyebrow eyebrow--compact">Legal</span>
        <h2>Policy library</h2>
        <p>
          Product-facing baseline templates for privacy, cookies, terms, enterprise processing,
          and sub-processor transparency.
        </p>
      </div>

      <div className="legal-nav">
        {legalNavigation.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`legal-nav__link${active ? " is-active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
