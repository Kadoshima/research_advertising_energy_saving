package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

type PlanRequest struct {
	Persona   string   `json:"persona"`
	Channels  []string `json:"channels"`
	Goal      string   `json:"goal"`
	Timeframe string   `json:"timeframe"` // e.g., "today", "weekly"
}

type PlanItem struct {
	Channel string `json:"channel"`
	When    string `json:"when"`   // ISO8601 string
	Summary string `json:"summary"` // short description
}

type PlanResponse struct {
	Persona string     `json:"persona"`
	Items   []PlanItem `json:"items"`
}

type PostRequest struct {
	Persona string `json:"persona"`
	Channel string `json:"channel"`
	Content string `json:"content"`
}

type PostResponse struct {
	ID      string `json:"id"`
	Status  string `json:"status"`
	Channel string `json:"channel"`
}

func main() {
	addr := defaultAddr()
	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/plan", handlePlan)
	mux.HandleFunc("/post", handlePost)

	server := &http.Server{
		Addr:              addr,
		Handler:           logRequests(mux),
		ReadHeaderTimeout: 5 * time.Second,
	}

	log.Printf("backend listening on %s", addr)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("server error: %v", err)
	}
}

func defaultAddr() string {
	if v := os.Getenv("AUTOPILOT_BACKEND_ADDR"); v != "" {
		return v
	}
	return ":8080"
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func handlePlan(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req PlanRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON"})
		return
	}

	items := synthesizePlan(req)
	resp := PlanResponse{
		Persona: req.Persona,
		Items:   items,
	}
	writeJSON(w, http.StatusOK, resp)
}

func synthesizePlan(req PlanRequest) []PlanItem {
	var items []PlanItem
	now := time.Now()
	for i, ch := range req.Channels {
		when := now.Add(time.Duration(i) * time.Hour).UTC().Format(time.RFC3339)
		items = append(items, PlanItem{
			Channel: ch,
			When:    when,
			Summary: fmt.Sprintf("%s: %s [%s]", req.Persona, req.Goal, req.Timeframe),
		})
	}
	return items
}

func handlePost(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req PostRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON"})
		return
	}

	// Stub: accept and return a synthetic ID.
	resp := PostResponse{
		ID:      fmt.Sprintf("%s-%d", req.Channel, time.Now().UnixNano()),
		Status:  "queued",
		Channel: req.Channel,
	}
	writeJSON(w, http.StatusAccepted, resp)
}

func logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %s", r.Method, r.URL.Path, time.Since(start))
	})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
