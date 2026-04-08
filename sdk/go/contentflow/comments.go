package contentflow

import (
	"context"
	"net/url"
	"strconv"
)

// CommentsResource provides access to comment autopilot endpoints.
type CommentsResource struct{ c *Client }

// CollectRequest is the body for collecting comments from a platform post.
type CollectRequest struct {
	Platform       string            `json:"platform"`
	PlatformPostID string            `json:"platform_post_id"`
	Credentials    map[string]string `json:"credentials"`
}

// ReplyRequest is the body for generating an AI reply.
type ReplyRequest struct {
	Credentials map[string]string `json:"credentials"`
	Context     string            `json:"context,omitempty"`
}

// Comment represents a collected comment.
type Comment struct {
	ID                string  `json:"id"`
	UserID            string  `json:"user_id"`
	Platform          string  `json:"platform"`
	PlatformPostID    string  `json:"platform_post_id"`
	PlatformCommentID string  `json:"platform_comment_id"`
	AuthorName        string  `json:"author_name"`
	Text              string  `json:"text"`
	AIReply           *string `json:"ai_reply"`
	ReplyStatus       string  `json:"reply_status"`
	CreatedAt         string  `json:"created_at"`
	UpdatedAt         string  `json:"updated_at"`
}

// CommentList is a paginated list of comments.
type CommentList struct {
	Data  []Comment `json:"data"`
	Total int       `json:"total"`
	Page  int       `json:"page"`
	Limit int       `json:"limit"`
}

// ReplyResponse contains the result of an AI reply attempt.
type ReplyResponse struct {
	Success        bool    `json:"success"`
	AIReply        *string `json:"ai_reply"`
	PlatformReplyID *string `json:"platform_reply_id"`
	Error          *string `json:"error"`
}

// Collect fetches and stores comments from a platform post.
func (r *CommentsResource) Collect(ctx context.Context, req *CollectRequest) ([]Comment, error) {
	var out []Comment
	err := r.c.request(ctx, "POST", "/comments/collect", nil, req, &out)
	return out, err
}

// ListParams are optional parameters for listing comments.
type ListCommentsParams struct {
	Platform       string
	PlatformPostID string
	ReplyStatus    string
	Page           int
	Limit          int
}

// List returns a paginated list of collected comments.
func (r *CommentsResource) List(ctx context.Context, params *ListCommentsParams) (*CommentList, error) {
	q := url.Values{}
	if params != nil {
		if params.Platform != "" {
			q.Set("platform", params.Platform)
		}
		if params.PlatformPostID != "" {
			q.Set("platform_post_id", params.PlatformPostID)
		}
		if params.ReplyStatus != "" {
			q.Set("reply_status", params.ReplyStatus)
		}
		if params.Page > 0 {
			q.Set("page", strconv.Itoa(params.Page))
		}
		if params.Limit > 0 {
			q.Set("limit", strconv.Itoa(params.Limit))
		}
	}
	var out CommentList
	err := r.c.request(ctx, "GET", "/comments", q, nil, &out)
	return &out, err
}

// Get returns a single comment by ID.
func (r *CommentsResource) Get(ctx context.Context, id string) (*Comment, error) {
	var out Comment
	err := r.c.request(ctx, "GET", "/comments/"+id, nil, nil, &out)
	return &out, err
}

// Reply generates an AI reply and posts it to the platform.
func (r *CommentsResource) Reply(ctx context.Context, id string, req *ReplyRequest) (*ReplyResponse, error) {
	var out ReplyResponse
	err := r.c.request(ctx, "POST", "/comments/"+id+"/reply", nil, req, &out)
	return &out, err
}
