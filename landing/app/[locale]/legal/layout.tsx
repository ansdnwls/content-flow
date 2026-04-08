import type { ReactNode } from "react";

import { LegalNav } from "@/components/legal-nav";
import { LEGAL_LAST_UPDATED } from "@/lib/legal-content";

export default function LegalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="legal-page page">
      <div className="legal-layout">
        <aside className="legal-layout__sidebar">
          <LegalNav />
        </aside>

        <main className="legal-layout__content">
          <div className="legal-layout__topline">
            <span className="pill">ContentFlow legal center</span>
            <span className="legal-layout__updated">Last updated: {LEGAL_LAST_UPDATED}</span>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
