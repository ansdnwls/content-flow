import { createHmac } from "node:crypto";
import { describe, expect, it } from "vitest";
import { verifySignature, WebhookVerificationError } from "../src/webhooks.js";

const SECRET = "whsec_test_secret";
const BODY = '{"event":"post.published","data":{"id":"p1"}}';

function sign(body: string, secret: string, timestamp: string): string {
  const payload = `${timestamp}.${body}`;
  const digest = createHmac("sha256", secret).update(payload).digest("hex");
  return `sha256=${digest}`;
}

const NOW = Math.floor(Date.now() / 1000);

describe("verifySignature", () => {
  it("accepts a valid signature", async () => {
    const ts = String(NOW);
    const sig = sign(BODY, SECRET, ts);
    const result = await verifySignature(BODY, sig, SECRET, ts, {
      currentTime: NOW,
    });
    expect(result).toBe(true);
  });

  it("rejects an invalid signature", async () => {
    const ts = String(NOW);
    await expect(
      verifySignature(BODY, "sha256=bad", SECRET, ts, { currentTime: NOW }),
    ).rejects.toThrow(WebhookVerificationError);
  });

  it("rejects a stale timestamp", async () => {
    const staleTs = String(NOW - 600);
    const sig = sign(BODY, SECRET, staleTs);
    await expect(
      verifySignature(BODY, sig, SECRET, staleTs, { currentTime: NOW }),
    ).rejects.toThrow(WebhookVerificationError);
  });
});
