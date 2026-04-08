"use client";

import { useState, useRef, useEffect } from "react";
import { useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { Globe } from "lucide-react";

const LOCALES = [
  { code: "ko", label: "한국어" },
  { code: "en", label: "English" },
  { code: "ja", label: "日本語" },
] as const;

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function switchLocale(code: string) {
    router.replace(pathname, { locale: code });
    setOpen(false);
  }

  const current = LOCALES.find((l) => l.code === locale);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="btn-secondary min-w-[48px] px-3 flex items-center gap-2"
        aria-label="Switch language"
      >
        <Globe size={16} />
        <span className="hidden sm:inline text-xs">{current?.label}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 z-50 w-36 overflow-hidden rounded-2xl border border-border/70 bg-card/95 backdrop-blur-xl shadow-[0_24px_70px_rgba(7,4,9,0.32)]">
          {LOCALES.map((l) => (
            <button
              key={l.code}
              onClick={() => switchLocale(l.code)}
              className={`w-full px-4 py-2.5 text-left text-sm transition-colors hover:bg-card-hover/60 ${
                l.code === locale ? "text-accent font-semibold" : "text-text"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
