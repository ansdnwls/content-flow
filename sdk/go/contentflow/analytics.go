package contentflow

import (
	"context"
	"net/url"
	"strconv"
)

// AnalyticsResource provides access to analytics endpoints.
type AnalyticsResource struct{ c *Client }

// DashboardResponse contains aggregated metrics for a period.
type DashboardResponse struct {
	Period           string  `json:"period"`
	Days             int     `json:"days"`
	SnapshotCount    int     `json:"snapshot_count"`
	TotalViews       int     `json:"total_views"`
	TotalLikes       int     `json:"total_likes"`
	TotalComments    int     `json:"total_comments"`
	TotalShares      int     `json:"total_shares"`
	TotalImpressions int     `json:"total_impressions"`
	TotalReach       int     `json:"total_reach"`
	EngagementRate   float64 `json:"engagement_rate"`
}

// AnalyticsSummary contains counts of posts and videos by status.
type AnalyticsSummary struct {
	PostCounts  map[string]int `json:"post_counts"`
	VideoCounts map[string]int `json:"video_counts"`
}

// PlatformMetrics contains per-platform aggregated metrics.
type PlatformMetrics struct {
	Platform         string  `json:"platform"`
	TotalViews       int     `json:"total_views"`
	TotalLikes       int     `json:"total_likes"`
	TotalComments    int     `json:"total_comments"`
	TotalShares      int     `json:"total_shares"`
	TotalImpressions int     `json:"total_impressions"`
	TotalReach       int     `json:"total_reach"`
	EngagementRate   float64 `json:"engagement_rate"`
}

// TopPost represents a top-performing post.
type TopPost struct {
	Platform       string  `json:"platform"`
	PlatformPostID string  `json:"platform_post_id"`
	Views          int     `json:"views"`
	Likes          int     `json:"likes"`
	Comments       int     `json:"comments"`
	Shares         int     `json:"shares"`
	EngagementRate float64 `json:"engagement_rate"`
	SnapshotDate   string  `json:"snapshot_date"`
}

// GrowthEntry represents daily follower counts by platform.
type GrowthEntry struct {
	Date                string         `json:"date"`
	FollowersByPlatform map[string]int `json:"followers_by_platform"`
}

// Dashboard returns aggregated analytics for the given period.
func (r *AnalyticsResource) Dashboard(ctx context.Context, period string) (*DashboardResponse, error) {
	q := url.Values{}
	if period != "" {
		q.Set("period", period)
	}
	var out DashboardResponse
	err := r.c.request(ctx, "GET", "/analytics", q, nil, &out)
	return &out, err
}

// Summary returns counts of posts and videos by status.
func (r *AnalyticsResource) Summary(ctx context.Context) (*AnalyticsSummary, error) {
	var out AnalyticsSummary
	err := r.c.request(ctx, "GET", "/analytics/summary", nil, nil, &out)
	return &out, err
}

// Platforms returns per-platform metrics for comparison.
func (r *AnalyticsResource) Platforms(ctx context.Context, period string) ([]PlatformMetrics, error) {
	q := url.Values{}
	if period != "" {
		q.Set("period", period)
	}
	var out []PlatformMetrics
	err := r.c.request(ctx, "GET", "/analytics/platforms", q, nil, &out)
	return out, err
}

// TopPostsParams are optional parameters for fetching top posts.
type TopPostsParams struct {
	Period string
	Limit  int
	SortBy string
}

// TopPosts returns top-performing posts ranked by the specified metric.
func (r *AnalyticsResource) TopPosts(ctx context.Context, params *TopPostsParams) ([]TopPost, error) {
	q := url.Values{}
	if params != nil {
		if params.Period != "" {
			q.Set("period", params.Period)
		}
		if params.Limit > 0 {
			q.Set("limit", strconv.Itoa(params.Limit))
		}
		if params.SortBy != "" {
			q.Set("sort_by", params.SortBy)
		}
	}
	var out []TopPost
	err := r.c.request(ctx, "GET", "/analytics/top-posts", q, nil, &out)
	return out, err
}

// Growth returns daily follower/subscriber counts by platform.
func (r *AnalyticsResource) Growth(ctx context.Context, period string) ([]GrowthEntry, error) {
	q := url.Values{}
	if period != "" {
		q.Set("period", period)
	}
	var out []GrowthEntry
	err := r.c.request(ctx, "GET", "/analytics/growth", q, nil, &out)
	return out, err
}
