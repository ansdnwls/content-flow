"use client";

import { useFormatter, useLocale } from "next-intl";

/**
 * Locale-aware formatting utilities built on next-intl's useFormatter.
 */

export function useFormatDate() {
  const format = useFormatter();
  const locale = useLocale();

  return {
    /** "April 8, 2026" / "2026년 4월 8일" / "2026年4月8日" */
    long(date: Date | string) {
      return format.dateTime(new Date(date), { dateStyle: "long" });
    },

    /** "Apr 8, 2026" / "2026. 4. 8." / "2026/04/08" */
    short(date: Date | string) {
      return format.dateTime(new Date(date), { dateStyle: "medium" });
    },

    /** "04/08/2026 14:30" */
    dateTime(date: Date | string) {
      return format.dateTime(new Date(date), {
        dateStyle: "short",
        timeStyle: "short",
      });
    },

    /** "2 hours ago" / "2시간 전" / "2時間前" */
    relative(date: Date | string) {
      return format.relativeTime(new Date(date));
    },

    /** "14:30" / "오후 2:30" / "14:30" */
    time(date: Date | string) {
      return format.dateTime(new Date(date), { timeStyle: "short" });
    },

    /** Current locale code */
    locale,
  };
}

export function useFormatNumber() {
  const format = useFormatter();

  return {
    /** "1,234,567" / "1,234,567" / "1,234,567" */
    integer(value: number) {
      return format.number(value, { maximumFractionDigits: 0 });
    },

    /** "$29.00" / "US$29.00" / "$29.00" */
    currency(value: number, currency = "USD") {
      return format.number(value, { style: "currency", currency });
    },

    /** "42%" */
    percent(value: number) {
      return format.number(value / 100, { style: "percent" });
    },

    /** "1.2K" / "1.2万" compact notation */
    compact(value: number) {
      return format.number(value, { notation: "compact" });
    },
  };
}
