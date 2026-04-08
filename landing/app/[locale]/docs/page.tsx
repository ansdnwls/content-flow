import { permanentRedirect } from "next/navigation";

const DOCS_URL = "https://docs.contentflow.dev";

export default function DocsPage() {
  permanentRedirect(DOCS_URL);
}
