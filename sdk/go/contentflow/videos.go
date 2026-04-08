package contentflow

import "context"

// VideosResource provides access to video generation endpoints.
type VideosResource struct{ c *Client }

// GenerateVideoRequest is the body for generating a new video.
type GenerateVideoRequest struct {
	Topic       string       `json:"topic"`
	Mode        string       `json:"mode,omitempty"`
	Language    string       `json:"language,omitempty"`
	Format      string       `json:"format,omitempty"`
	Style       string       `json:"style,omitempty"`
	AutoPublish *AutoPublish `json:"auto_publish,omitempty"`
}

// AutoPublish configures automatic publishing after video generation.
type AutoPublish struct {
	Enabled      bool     `json:"enabled"`
	Platforms    []string `json:"platforms"`
	ScheduledFor *string  `json:"scheduled_for,omitempty"`
}

// Video represents a video generation job.
type Video struct {
	ID            string `json:"id"`
	Topic         string `json:"topic"`
	Mode          string `json:"mode"`
	Status        string `json:"status"`
	ProviderJobID string `json:"provider_job_id"`
	OutputURL     string `json:"output_url"`
	CreatedAt     string `json:"created_at"`
	UpdatedAt     string `json:"updated_at"`
}

// Generate starts a new video generation job.
func (r *VideosResource) Generate(ctx context.Context, req *GenerateVideoRequest) (*Video, error) {
	var out Video
	err := r.c.request(ctx, "POST", "/videos", nil, req, &out)
	return &out, err
}

// Get returns the status of a video generation job.
func (r *VideosResource) Get(ctx context.Context, id string) (*Video, error) {
	var out Video
	err := r.c.request(ctx, "GET", "/videos/"+id, nil, nil, &out)
	return &out, err
}
