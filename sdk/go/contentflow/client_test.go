package contentflow

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// helper: start a test server that returns a canned JSON response.
func testServer(t *testing.T, wantMethod, wantPath string, status int, body interface{}) *Client {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != wantMethod {
			t.Errorf("method = %s, want %s", r.Method, wantMethod)
		}
		if r.URL.Path != "/api/v1"+wantPath {
			t.Errorf("path = %s, want /api/v1%s", r.URL.Path, wantPath)
		}
		if r.Header.Get("X-API-Key") != "test-key" {
			t.Errorf("missing or wrong X-API-Key header")
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		json.NewEncoder(w).Encode(body)
	}))
	t.Cleanup(srv.Close)
	return New("test-key", WithBaseURL(srv.URL))
}

// ---------- Posts ----------

func TestPostsCreate(t *testing.T) {
	text := "Hello world"
	c := testServer(t, "POST", "/posts", 200, Post{
		ID:     "post-1",
		Status: "pending",
		Text:   &text,
	})
	post, err := c.Posts.Create(context.Background(), &CreatePostRequest{
		Text:      &text,
		Platforms: []string{"youtube"},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if post.ID != "post-1" {
		t.Errorf("ID = %q, want post-1", post.ID)
	}
}

func TestPostsGet(t *testing.T) {
	c := testServer(t, "GET", "/posts/post-1", 200, Post{ID: "post-1", Status: "published"})
	post, err := c.Posts.Get(context.Background(), "post-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if post.Status != "published" {
		t.Errorf("Status = %q, want published", post.Status)
	}
}

func TestPostsList(t *testing.T) {
	c := testServer(t, "GET", "/posts", 200, PostList{
		Data:  []Post{{ID: "p1"}, {ID: "p2"}},
		Total: 2, Page: 1, Limit: 50,
	})
	list, err := c.Posts.List(context.Background(), nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(list.Data) != 2 {
		t.Errorf("len(Data) = %d, want 2", len(list.Data))
	}
}

func TestPostsCancel(t *testing.T) {
	c := testServer(t, "DELETE", "/posts/post-1", 200, Post{ID: "post-1", Status: "cancelled"})
	post, err := c.Posts.Cancel(context.Background(), "post-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if post.Status != "cancelled" {
		t.Errorf("Status = %q, want cancelled", post.Status)
	}
}

// ---------- Videos ----------

func TestVideosGenerate(t *testing.T) {
	c := testServer(t, "POST", "/videos", 200, Video{ID: "vid-1", Status: "queued"})
	vid, err := c.Videos.Generate(context.Background(), &GenerateVideoRequest{Topic: "Go tips"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if vid.ID != "vid-1" {
		t.Errorf("ID = %q, want vid-1", vid.ID)
	}
}

func TestVideosGet(t *testing.T) {
	c := testServer(t, "GET", "/videos/vid-1", 200, Video{ID: "vid-1", Status: "completed"})
	vid, err := c.Videos.Get(context.Background(), "vid-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if vid.Status != "completed" {
		t.Errorf("Status = %q, want completed", vid.Status)
	}
}

// ---------- Accounts ----------

func TestAccountsList(t *testing.T) {
	c := testServer(t, "GET", "/accounts", 200, AccountList{
		Data:  []Account{{ID: "acc-1", Platform: "youtube", Handle: "@test"}},
		Total: 1,
	})
	list, err := c.Accounts.List(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if list.Total != 1 {
		t.Errorf("Total = %d, want 1", list.Total)
	}
}

func TestAccountsConnect(t *testing.T) {
	c := testServer(t, "POST", "/accounts/connect/youtube", 200, ConnectResponse{
		AuthorizeURL: "https://accounts.google.com/o/oauth2/auth?...",
	})
	resp, err := c.Accounts.Connect(context.Background(), "youtube")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.AuthorizeURL == "" {
		t.Error("AuthorizeURL is empty")
	}
}

func TestAccountsDisconnect(t *testing.T) {
	c := testServer(t, "DELETE", "/accounts/acc-1", 200, Account{ID: "acc-1", Platform: "youtube"})
	acc, err := c.Accounts.Disconnect(context.Background(), "acc-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if acc.ID != "acc-1" {
		t.Errorf("ID = %q, want acc-1", acc.ID)
	}
}

// ---------- Analytics ----------

func TestAnalyticsDashboard(t *testing.T) {
	c := testServer(t, "GET", "/analytics", 200, DashboardResponse{
		Period: "30d", Days: 30, TotalViews: 1000,
	})
	dash, err := c.Analytics.Dashboard(context.Background(), "30d")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if dash.TotalViews != 1000 {
		t.Errorf("TotalViews = %d, want 1000", dash.TotalViews)
	}
}

func TestAnalyticsSummary(t *testing.T) {
	c := testServer(t, "GET", "/analytics/summary", 200, AnalyticsSummary{
		PostCounts:  map[string]int{"published": 5},
		VideoCounts: map[string]int{"completed": 3},
	})
	summary, err := c.Analytics.Summary(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if summary.PostCounts["published"] != 5 {
		t.Errorf("PostCounts[published] = %d, want 5", summary.PostCounts["published"])
	}
}

func TestAnalyticsTopPosts(t *testing.T) {
	c := testServer(t, "GET", "/analytics/top-posts", 200, []TopPost{
		{Platform: "youtube", Views: 500},
	})
	posts, err := c.Analytics.TopPosts(context.Background(), &TopPostsParams{
		Period: "7d", Limit: 5, SortBy: "views",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(posts) != 1 {
		t.Errorf("len = %d, want 1", len(posts))
	}
}

// ---------- Comments ----------

func TestCommentsCollect(t *testing.T) {
	c := testServer(t, "POST", "/comments/collect", 200, []Comment{
		{ID: "c1", Platform: "youtube", Text: "Great video!"},
	})
	comments, err := c.Comments.Collect(context.Background(), &CollectRequest{
		Platform:       "youtube",
		PlatformPostID: "abc123",
		Credentials:    map[string]string{"access_token": "tok"},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(comments) != 1 {
		t.Errorf("len = %d, want 1", len(comments))
	}
}

func TestCommentsReply(t *testing.T) {
	reply := "Thanks!"
	c := testServer(t, "POST", "/comments/c1/reply", 200, ReplyResponse{
		Success: true, AIReply: &reply,
	})
	resp, err := c.Comments.Reply(context.Background(), "c1", &ReplyRequest{
		Credentials: map[string]string{"access_token": "tok"},
		Context:     "Python tips video",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !resp.Success {
		t.Error("expected Success=true")
	}
}

// ---------- Bombs ----------

func TestBombsCreate(t *testing.T) {
	c := testServer(t, "POST", "/bombs", 200, Bomb{
		ID: "bomb-1", Topic: "Go tips", Status: "queued",
	})
	bomb, err := c.Bombs.Create(context.Background(), &CreateBombRequest{Topic: "Go tips"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if bomb.Status != "queued" {
		t.Errorf("Status = %q, want queued", bomb.Status)
	}
}

func TestBombsPublish(t *testing.T) {
	c := testServer(t, "POST", "/bombs/bomb-1/publish", 200, Bomb{
		ID: "bomb-1", Status: "published",
	})
	bomb, err := c.Bombs.Publish(context.Background(), "bomb-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if bomb.Status != "published" {
		t.Errorf("Status = %q, want published", bomb.Status)
	}
}

// ---------- Webhooks ----------

func TestWebhooksListDeliveries(t *testing.T) {
	c := testServer(t, "GET", "/webhooks/wh-1/deliveries", 200, WebhookDeliveryList{
		Data:  []WebhookDelivery{{ID: "d1", Status: "delivered"}},
		Total: 1, Page: 1, Limit: 50,
	})
	list, err := c.Webhooks.ListDeliveries(context.Background(), "wh-1", nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if list.Total != 1 {
		t.Errorf("Total = %d, want 1", list.Total)
	}
}

func TestWebhooksRedeliver(t *testing.T) {
	c := testServer(t, "POST", "/webhooks/wh-1/redeliver", 200, WebhookReplayResponse{
		Success:  true,
		Delivery: WebhookDelivery{ID: "d1", Status: "delivered"},
	})
	resp, err := c.Webhooks.Redeliver(context.Background(), "wh-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !resp.Success {
		t.Error("expected Success=true")
	}
}

// ---------- Webhook signature verification ----------

func TestVerifySignature_Valid(t *testing.T) {
	body := []byte(`{"post_id":"p1"}`)
	timestamp := "1700000000"
	secret := "whsec_test"
	sig := buildSignature(secret, body, timestamp)

	if err := VerifySignature(body, sig, timestamp, secret); err != nil {
		t.Fatalf("expected valid signature, got: %v", err)
	}
}

func TestVerifySignature_Invalid(t *testing.T) {
	body := []byte(`{"post_id":"p1"}`)
	err := VerifySignature(body, "sha256=bad", "1700000000", "whsec_test")
	if err != ErrInvalidSignature {
		t.Fatalf("expected ErrInvalidSignature, got: %v", err)
	}
}

// ---------- Error handling ----------

func TestAuthError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(401)
		w.Write([]byte(`{"detail":"Invalid API key"}`))
	}))
	t.Cleanup(srv.Close)

	c := New("bad-key", WithBaseURL(srv.URL))
	_, err := c.Posts.Get(context.Background(), "post-1")
	if err == nil {
		t.Fatal("expected error")
	}
	authErr, ok := err.(*AuthError)
	if !ok {
		t.Fatalf("expected *AuthError, got %T", err)
	}
	if authErr.StatusCode != 401 {
		t.Errorf("StatusCode = %d, want 401", authErr.StatusCode)
	}
}

func TestRateLimitError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Retry-After", "60")
		w.WriteHeader(429)
		w.Write([]byte(`{"detail":"Rate limit exceeded"}`))
	}))
	t.Cleanup(srv.Close)

	c := New("test-key", WithBaseURL(srv.URL))
	_, err := c.Posts.Get(context.Background(), "post-1")
	if err == nil {
		t.Fatal("expected error")
	}
	rlErr, ok := err.(*RateLimitError)
	if !ok {
		t.Fatalf("expected *RateLimitError, got %T", err)
	}
	if rlErr.RetryAfter != "60" {
		t.Errorf("RetryAfter = %q, want 60", rlErr.RetryAfter)
	}
}

func TestAPIError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
		w.Write([]byte(`{"detail":"Not found"}`))
	}))
	t.Cleanup(srv.Close)

	c := New("test-key", WithBaseURL(srv.URL))
	_, err := c.Posts.Get(context.Background(), "post-1")
	if err == nil {
		t.Fatal("expected error")
	}
	apiErr, ok := err.(*APIError)
	if !ok {
		t.Fatalf("expected *APIError, got %T", err)
	}
	if apiErr.Detail != "Not found" {
		t.Errorf("Detail = %q, want 'Not found'", apiErr.Detail)
	}
}

// ---------- Client options ----------

func TestWithBaseURL(t *testing.T) {
	c := New("key", WithBaseURL("https://custom.api.com"))
	if c.baseURL != "https://custom.api.com" {
		t.Errorf("baseURL = %q, want https://custom.api.com", c.baseURL)
	}
}

func TestAllResourcesInitialized(t *testing.T) {
	c := New("key")
	if c.Posts == nil {
		t.Error("Posts is nil")
	}
	if c.Videos == nil {
		t.Error("Videos is nil")
	}
	if c.Accounts == nil {
		t.Error("Accounts is nil")
	}
	if c.Analytics == nil {
		t.Error("Analytics is nil")
	}
	if c.Comments == nil {
		t.Error("Comments is nil")
	}
	if c.Bombs == nil {
		t.Error("Bombs is nil")
	}
	if c.Webhooks == nil {
		t.Error("Webhooks is nil")
	}
}
