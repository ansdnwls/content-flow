// Package contentflow — consolidated type aliases and shared types.
//
// Resource-specific types live in their own files (posts.go, videos.go, etc.).
// This file provides additional shared types and type aliases for convenience.
package contentflow

// Pagination is a generic pagination envelope.
type Pagination struct {
	Total int `json:"total"`
	Page  int `json:"page"`
	Limit int `json:"limit"`
}

// APIResponse wraps a generic API response with optional error detail.
type APIResponse struct {
	Success bool   `json:"success"`
	Detail  string `json:"detail,omitempty"`
}

// WebhookEvent represents an incoming webhook event payload.
type WebhookEvent struct {
	ID        string                 `json:"id"`
	EventType string                 `json:"event_type"`
	Data      map[string]interface{} `json:"data"`
	Timestamp string                 `json:"timestamp"`
}
