package contentflow

import "fmt"

// APIError represents a non-2xx response from the ContentFlow API.
type APIError struct {
	StatusCode int
	Detail     string
	Body       []byte
}

func (e *APIError) Error() string {
	if e.Detail != "" {
		return fmt.Sprintf("contentflow: HTTP %d — %s", e.StatusCode, e.Detail)
	}
	return fmt.Sprintf("contentflow: HTTP %d", e.StatusCode)
}

// AuthError is returned for 401 Unauthorized responses.
type AuthError struct{ APIError }

// RateLimitError is returned for 429 Too Many Requests responses.
type RateLimitError struct {
	APIError
	RetryAfter string
}
