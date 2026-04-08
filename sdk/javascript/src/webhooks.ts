/**
 * Webhook signature verification helpers for the ContentFlow JavaScript SDK.
 */

const SIGNATURE_PREFIX = "sha256=";
const DEFAULT_TOLERANCE_SECONDS = 300;

export class WebhookVerificationError extends Error {
  constructor(message = "Signature verification failed") {
    super(message);
    this.name = "WebhookVerificationError";
  }
}

export interface VerifySignatureOptions {
  toleranceSeconds?: number;
  currentTime?: number;
}

function getCrypto(): NonNullable<typeof globalThis.crypto> {
  if (typeof globalThis.crypto?.subtle === "undefined") {
    throw new WebhookVerificationError("Web Crypto API is not available");
  }
  return globalThis.crypto;
}

function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function timingSafeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) {
    return false;
  }

  let diff = 0;
  for (let i = 0; i < left.length; i += 1) {
    diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  }
  return diff === 0;
}

export async function verifySignature(
  body: string,
  signature: string,
  secret: string,
  timestamp: string,
  options?: VerifySignatureOptions,
): Promise<boolean> {
  if (!signature.startsWith(SIGNATURE_PREFIX)) {
    throw new WebhookVerificationError("Missing sha256= prefix");
  }

  const signedAt = Number(timestamp);
  if (Number.isNaN(signedAt)) {
    throw new WebhookVerificationError("Invalid timestamp");
  }

  const now = options?.currentTime ?? Math.floor(Date.now() / 1000);
  const tolerance = options?.toleranceSeconds ?? DEFAULT_TOLERANCE_SECONDS;
  if (Math.abs(now - signedAt) > tolerance) {
    throw new WebhookVerificationError("Timestamp outside tolerance");
  }

  const crypto = getCrypto();
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signedPayload = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(`${timestamp}.${body}`),
  );
  const expected = `${SIGNATURE_PREFIX}${toHex(signedPayload)}`;

  if (!timingSafeEqual(expected, signature)) {
    throw new WebhookVerificationError();
  }

  return true;
}
