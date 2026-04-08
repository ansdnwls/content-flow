import type { Metadata } from "next";

import { LegalDocument } from "@/components/legal-document";
import { privacyDocument } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "Privacy Policy | ContentFlow",
  description: privacyDocument.summary,
};

export default function PrivacyPage() {
  return <LegalDocument document={privacyDocument} />;
}
