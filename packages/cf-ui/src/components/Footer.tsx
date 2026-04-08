import React from "react";

interface FooterProps {
  readonly name: string;
  readonly domain?: string;
}

export function Footer({ name, domain }: FooterProps) {
  const year = new Date().getFullYear();
  return (
    <footer className="py-12 px-6 border-t border-[var(--color-text)]/10">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="text-[var(--color-text)]/70 text-sm">
          &copy; {year} {name}. All rights reserved.
        </div>
        <div className="flex gap-6 text-sm text-[var(--color-text)]/50">
          <a href="/privacy" className="hover:text-[var(--color-text)] transition-colors">
            Privacy
          </a>
          <a href="/terms" className="hover:text-[var(--color-text)] transition-colors">
            Terms
          </a>
          {domain && (
            <a
              href={`https://${domain}`}
              className="hover:text-[var(--color-text)] transition-colors"
            >
              {domain}
            </a>
          )}
        </div>
      </div>
    </footer>
  );
}
