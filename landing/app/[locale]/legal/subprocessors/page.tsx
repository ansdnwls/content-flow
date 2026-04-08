import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal-document";
import { subprocessorsDocument } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "Sub-processors | ContentFlow",
  description: subprocessorsDocument.summary,
};

export default function SubprocessorsPage() {
  return <LegalDocument document={subprocessorsDocument} />;
}
