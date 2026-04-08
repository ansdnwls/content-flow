import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal-document";
import { dpaDocument } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "DPA Template | ContentFlow",
  description: dpaDocument.summary,
};

export default function DpaPage() {
  return <LegalDocument document={dpaDocument} />;
}
