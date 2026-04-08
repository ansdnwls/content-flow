# Webhook Guarantees

ContentFlow webhooks are delivered with an at-least-once guarantee.

What this means:

- A successful delivery is cached with a 24 hour idempotency window per `webhook_id + event_id`.
- Failed deliveries are retried with backoff at `1 minute`, `5 minutes`, `30 minutes`, `2 hours`, and `6 hours`.
- After the final retry attempt, the delivery is moved to the dead letter queue.

Receiver guidance:

- Treat webhook handlers as idempotent.
- Deduplicate on the `X-ContentFlow-Event-Id` header.
- Return a `2xx` response only after your receiver has safely accepted the event.
- If you trigger a manual replay, expect a replay-specific event ID.

Headers:

- `X-ContentFlow-Event`: logical event name such as `post.published`
- `X-ContentFlow-Event-Id`: stable event identifier for retries
- `X-ContentFlow-Timestamp`: signing timestamp
- `X-ContentFlow-Signature`: HMAC-SHA256 signature
