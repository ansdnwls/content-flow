package contentflow

import "context"

// BombsResource provides access to content bomb endpoints.
type BombsResource struct{ c *Client }

// CreateBombRequest is the body for creating a content bomb.
type CreateBombRequest struct {
	Topic string `json:"topic"`
}

// Bomb represents a content bomb job.
type Bomb struct {
	ID               string                 `json:"id"`
	Topic            string                 `json:"topic"`
	Status           string                 `json:"status"`
	PlatformContents map[string]interface{} `json:"platform_contents"`
	CreatedAt        string                 `json:"created_at"`
	UpdatedAt        string                 `json:"updated_at"`
}

// Create creates a new content bomb from a single topic.
func (r *BombsResource) Create(ctx context.Context, req *CreateBombRequest) (*Bomb, error) {
	var out Bomb
	err := r.c.request(ctx, "POST", "/bombs", nil, req, &out)
	return &out, err
}

// Get returns the status and generated content for a bomb.
func (r *BombsResource) Get(ctx context.Context, id string) (*Bomb, error) {
	var out Bomb
	err := r.c.request(ctx, "GET", "/bombs/"+id, nil, nil, &out)
	return &out, err
}

// Publish queues the generated platform variants for publication.
func (r *BombsResource) Publish(ctx context.Context, id string) (*Bomb, error) {
	var out Bomb
	err := r.c.request(ctx, "POST", "/bombs/"+id+"/publish", nil, nil, &out)
	return &out, err
}
