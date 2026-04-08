import { CFEngine } from "@contentflow/engine";
import type { VerticalConfig } from "@contentflow/config";
import config from "../../config.json";

const API_URL =
  process.env.NEXT_PUBLIC_CF_API_URL ??
  (config as unknown as VerticalConfig).backend?.base_url ??
  "http://localhost:8000";

const API_KEY = process.env.CF_API_KEY ?? "";

export const engine = new CFEngine({
  apiUrl: API_URL,
  apiKey: API_KEY,
  config: config as unknown as VerticalConfig,
});

export { CFEngine } from "@contentflow/engine";
export type {
  YtBoostChannel,
  YtBoostShort,
  PendingComment,
  ShortsListResponse,
  PendingCommentListResponse,
} from "@contentflow/engine";
