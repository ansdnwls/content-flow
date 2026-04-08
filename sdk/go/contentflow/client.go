// Package contentflow provides a Go client for the ContentFlow API.
//
// Usage:
//
//	cf := contentflow.New("cf_live_xxx")
//	post, err := cf.Posts.Create(ctx, &contentflow.CreatePostRequest{
//	    Text:      strPtr("Hello"),
//	    Platforms: []string{"youtube", "tiktok"},
//	})
package contentflow

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

const (
	defaultBaseURL = "https://contentflow-api.railway.app"
	defaultTimeout = 30 * time.Second
	userAgent      = "contentflow-go/0.2.0"
)

// Client is the top-level ContentFlow API client.
type Client struct {
	apiKey  string
	baseURL string
	http    *http.Client

	Posts      *PostsResource
	Videos     *VideosResource
	Accounts   *AccountsResource
	Analytics  *AnalyticsResource
	Comments   *CommentsResource
	Bombs      *BombsResource
	Webhooks   *WebhooksResource
}

// Option configures a Client.
type Option func(*Client)

// WithBaseURL overrides the default API base URL.
func WithBaseURL(u string) Option { return func(c *Client) { c.baseURL = u } }

// WithHTTPClient overrides the default http.Client.
func WithHTTPClient(h *http.Client) Option { return func(c *Client) { c.http = h } }

// WithTimeout overrides the default request timeout.
func WithTimeout(d time.Duration) Option {
	return func(c *Client) { c.http.Timeout = d }
}

// New creates a new ContentFlow client.
func New(apiKey string, opts ...Option) *Client {
	c := &Client{
		apiKey:  apiKey,
		baseURL: defaultBaseURL,
		http:    &http.Client{Timeout: defaultTimeout},
	}
	for _, o := range opts {
		o(c)
	}
	c.Posts = &PostsResource{c: c}
	c.Videos = &VideosResource{c: c}
	c.Accounts = &AccountsResource{c: c}
	c.Analytics = &AnalyticsResource{c: c}
	c.Comments = &CommentsResource{c: c}
	c.Bombs = &BombsResource{c: c}
	c.Webhooks = &WebhooksResource{c: c}
	return c
}

// request builds, sends, and decodes an API request.
func (c *Client) request(
	ctx context.Context,
	method, path string,
	query url.Values,
	body any,
	out any,
) error {
	u := c.baseURL + "/api/v1" + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}

	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("contentflow: marshal body: %w", err)
		}
		bodyReader = bytes.NewReader(data)
	}

	req, err := http.NewRequestWithContext(ctx, method, u, bodyReader)
	if err != nil {
		return fmt.Errorf("contentflow: build request: %w", err)
	}
	req.Header.Set("X-API-Key", c.apiKey)
	req.Header.Set("User-Agent", userAgent)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("contentflow: do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("contentflow: read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return c.buildError(resp, respBody)
	}

	if out != nil && len(respBody) > 0 {
		if err := json.Unmarshal(respBody, out); err != nil {
			return fmt.Errorf("contentflow: decode response: %w", err)
		}
	}
	return nil
}

func (c *Client) buildError(resp *http.Response, body []byte) error {
	var parsed struct {
		Detail string `json:"detail"`
	}
	_ = json.Unmarshal(body, &parsed)

	base := APIError{
		StatusCode: resp.StatusCode,
		Detail:     parsed.Detail,
		Body:       body,
	}

	switch resp.StatusCode {
	case http.StatusUnauthorized:
		return &AuthError{APIError: base}
	case http.StatusTooManyRequests:
		return &RateLimitError{
			APIError:   base,
			RetryAfter: resp.Header.Get("Retry-After"),
		}
	default:
		return &base
	}
}
