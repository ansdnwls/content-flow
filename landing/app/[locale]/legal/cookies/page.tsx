import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal-document";
import { cookieDocument } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "Cookie Policy | ContentFlow",
  description: cookieDocument.summary,
};

export default function CookiesPage() {
  return <LegalDocument document={cookieDocument} />;
}
