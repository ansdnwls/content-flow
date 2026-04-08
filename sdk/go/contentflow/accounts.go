package contentflow

import "context"

// AccountsResource provides access to connected account endpoints.
type AccountsResource struct{ c *Client }

// Account represents a connected social media account.
type Account struct {
	ID             string                 `json:"id"`
	Platform       string                 `json:"platform"`
	Handle         string                 `json:"handle"`
	DisplayName    *string                `json:"display_name"`
	TokenExpiresAt *string                `json:"token_expires_at"`
	Metadata       map[string]interface{} `json:"metadata"`
}

// AccountList is a list of connected accounts.
type AccountList struct {
	Data  []Account `json:"data"`
	Total int       `json:"total"`
}

// ConnectResponse contains the OAuth authorization URL.
type ConnectResponse struct {
	AuthorizeURL string `json:"authorize_url"`
}

// List returns all connected accounts.
func (r *AccountsResource) List(ctx context.Context) (*AccountList, error) {
	var out AccountList
	err := r.c.request(ctx, "GET", "/accounts", nil, nil, &out)
	return &out, err
}

// Connect initiates an OAuth connection for the given platform.
func (r *AccountsResource) Connect(ctx context.Context, platform string) (*ConnectResponse, error) {
	var out ConnectResponse
	err := r.c.request(ctx, "POST", "/accounts/connect/"+platform, nil, nil, &out)
	return &out, err
}

// Disconnect removes a connected account.
func (r *AccountsResource) Disconnect(ctx context.Context, id string) (*Account, error) {
	var out Account
	err := r.c.request(ctx, "DELETE", "/accounts/"+id, nil, nil, &out)
	return &out, err
}
