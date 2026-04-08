package contentflow

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"net/url"
	"strconv"
)

// WebhooksResource provides access to webhook delivery endpoints.
type WebhooksResource struct{ c *Client }

// WebhookDelivery represents a webhook delivery attempt.
type WebhookDelivery struct {
	ID          string                 `json:"id"`
	WebhookID   string                 `json:"webhook_id"`
	Event       string                 `json:"event"`
	Payload     map[string]interface{} `json:"payload"`
	Status      string                 `json:"status"`
	Attempts    int                    `json:"attempts"`
	LastError   *string                `json:"last_error"`
	NextRetryAt *string                `json:"next_retry_at"`
	DeliveredAt *string                `json:"delivered_at"`
	CreatedAt   *string                `json:"created_at"`
	UpdatedAt   *string                `json:"updated_at"`
}

// WebhookDeliveryList is a paginated list of webhook deliveries.
type WebhookDeliveryList struct {
	Data  []WebhookDelivery `json:"data"`
	Total int               `json:"total"`
	Page  int               `json:"page"`
	Limit int               `json:"limit"`
}

// WebhookReplayResponse contains the result of a redeliver/replay request.
type WebhookReplayResponse struct {
	Success  bool            `json:"success"`
	Delivery WebhookDelivery `json:"delivery"`
}

// ListDeliveriesParams are optional parameters for listing deliveries.
type ListDeliveriesParams struct {
	Page  int
	Limit int
}

// ListDeliveries returns delivery history for a webhook.
func (r *WebhooksResource) ListDeliveries(ctx context.Context, webhookID string, params *ListDeliveriesParams) (*WebhookDeliveryList, error) {
	q := url.Values{}
	if params != nil {
		if params.Page > 0 {
			q.Set("page", strconv.Itoa(params.Page))
		}
		if params.Limit > 0 {
			q.Set("limit", strconv.Itoa(params.Limit))
		}
	}
	var out WebhookDeliveryList
	err := r.c.request(ctx, "GET", fmt.Sprintf("/webhooks/%s/deliveries", webhookID), q, nil, &out)
	return &out, err
}

// ListDeadLetters returns deliveries that exhausted retries.
func (r *WebhooksResource) ListDeadLetters(ctx context.Context, params *ListDeliveriesParams) (*WebhookDeliveryList, error) {
	q := url.Values{}
	if params != nil {
		if params.Page > 0 {
			q.Set("page", strconv.Itoa(params.Page))
		}
		if params.Limit > 0 {
			q.Set("limit", strconv.Itoa(params.Limit))
		}
	}
	var out WebhookDeliveryList
	err := r.c.request(ctx, "GET", "/webhooks/dead-letters", q, nil, &out)
	return &out, err
}

// Redeliver replays the most recent delivery for a webhook.
func (r *WebhooksResource) Redeliver(ctx context.Context, webhookID string) (*WebhookReplayResponse, error) {
	var out WebhookReplayResponse
	err := r.c.request(ctx, "POST", fmt.Sprintf("/webhooks/%s/redeliver", webhookID), nil, nil, &out)
	return &out, err
}

// Replay creates a fresh delivery attempt from a historical delivery.
func (r *WebhooksResource) Replay(ctx context.Context, deliveryID string) (*WebhookReplayResponse, error) {
	var out WebhookReplayResponse
	err := r.c.request(ctx, "POST", fmt.Sprintf("/webhooks/deliveries/%s/replay", deliveryID), nil, nil, &out)
	return &out, err
}

// ---------- Signature verification ----------

const signaturePrefix = "sha256="

// ErrInvalidSignature is returned when webhook signature verification fails.
var ErrInvalidSignature = errors.New("contentflow: invalid webhook signature")

// VerifySignature checks the HMAC-SHA256 signature of a webhook payload.
// body is the raw request body, signature is the X-ContentFlow-Signature
// header value, timestamp is the X-ContentFlow-Timestamp header value,
// and secret is the webhook signing secret.
func VerifySignature(body []byte, signature, timestamp, secret string) error {
	expected := buildSignature(secret, body, timestamp)
	if subtle.ConstantTimeCompare([]byte(expected), []byte(signature)) != 1 {
		return ErrInvalidSignature
	}
	return nil
}

func buildSignature(secret string, body []byte, timestamp string) string {
	signedPayload := fmt.Sprintf("%s.%s", timestamp, string(body))
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(signedPayload))
	return signaturePrefix + hex.EncodeToString(mac.Sum(nil))
}
