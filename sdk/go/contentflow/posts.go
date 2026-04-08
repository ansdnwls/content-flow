package contentflow

import (
	"context"
	"fmt"
	"net/url"
	"strconv"
)

// PostsResource provides access to post-related API endpoints.
type PostsResource struct{ c *Client }

// CreatePostRequest is the body for creating a new post.
type CreatePostRequest struct {
	Text            *string                `json:"text,omitempty"`
	Platforms       []string               `json:"platforms"`
	MediaUrls       []string               `json:"media_urls,omitempty"`
	MediaType       string                 `json:"media_type,omitempty"`
	ScheduledFor    *string                `json:"scheduled_for,omitempty"`
	PlatformOptions map[string]interface{} `json:"platform_options,omitempty"`
}

// PlatformStatus represents per-platform delivery status.
type PlatformStatus struct {
	Status         string  `json:"status"`
	PlatformPostID *string `json:"platform_post_id"`
}

// Post represents a publishing job.
type Post struct {
	ID           string                    `json:"id"`
	Status       string                    `json:"status"`
	Text         *string                   `json:"text"`
	MediaUrls    []string                  `json:"media_urls"`
	MediaType    string                    `json:"media_type"`
	ScheduledFor *string                   `json:"scheduled_for"`
	Platforms    map[string]PlatformStatus  `json:"platforms"`
	CreatedAt    string                    `json:"created_at"`
	UpdatedAt    string                    `json:"updated_at"`
}

// PostList is a paginated list of posts.
type PostList struct {
	Data  []Post `json:"data"`
	Total int    `json:"total"`
	Page  int    `json:"page"`
	Limit int    `json:"limit"`
}

// Create creates a new multi-platform publishing job.
func (r *PostsResource) Create(ctx context.Context, req *CreatePostRequest) (*Post, error) {
	var out Post
	err := r.c.request(ctx, "POST", "/posts", nil, req, &out)
	return &out, err
}

// Get returns a single post by ID.
func (r *PostsResource) Get(ctx context.Context, id string) (*Post, error) {
	var out Post
	err := r.c.request(ctx, "GET", "/posts/"+id, nil, nil, &out)
	return &out, err
}

// ListParams are optional parameters for listing posts.
type ListPostsParams struct {
	Page   int
	Limit  int
	Status string
}

// List returns a paginated list of posts.
func (r *PostsResource) List(ctx context.Context, params *ListPostsParams) (*PostList, error) {
	q := url.Values{}
	if params != nil {
		if params.Page > 0 {
			q.Set("page", strconv.Itoa(params.Page))
		}
		if params.Limit > 0 {
			q.Set("limit", strconv.Itoa(params.Limit))
		}
		if params.Status != "" {
			q.Set("status", params.Status)
		}
	}
	var out PostList
	err := r.c.request(ctx, "GET", "/posts", q, nil, &out)
	return &out, err
}

// Cancel cancels a pending or scheduled post.
func (r *PostsResource) Cancel(ctx context.Context, id string) (*Post, error) {
	var out Post
	err := r.c.request(ctx, "DELETE", fmt.Sprintf("/posts/%s", id), nil, nil, &out)
	return &out, err
}
