import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal-document";
import { termsDocument } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "Terms of Service | ContentFlow",
  description: termsDocument.summary,
};

export default function TermsPage() {
  return <LegalDocument document={termsDocument} />;
}
