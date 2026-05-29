// Command search exposes the brute-force word-search API over HTTP on :8003.
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"

	"multithreading-lab/go/search"
)

// parallelMode routes /search through the threaded variants (intra-file split
// for /file, nested per-length fan-out for /many) unless SEARCH_MODE=baseline,
// which restores the original per-endpoint behavior.
var parallelMode = os.Getenv("SEARCH_MODE") != "baseline"

// hint is the JSON shape of a positional hint in a request body.
type hint struct {
	Pos      int     `json:"pos"`
	Car      *string `json:"car"`
	Inverted bool    `json:"inverted"`
}

type searchFileRequest struct {
	Lang    string   `json:"lang"`
	NbCar   int      `json:"nb_car"`
	LstCar  []string `json:"lst_car"`
	LstHint []hint   `json:"lst_hint"`
	Strict  bool     `json:"strict"`
}

type searchManyRequest struct {
	Lang    string `json:"lang"`
	Cars    string `json:"cars"`
	LstHint []hint `json:"lst_hint"`
}

type searchResponse struct {
	Words []string `json:"words"`
	Count int      `json:"count"`
}

// toSearchHints converts request hints into the search package's Hint type.
func toSearchHints(hints []hint) []search.Hint {
	out := make([]search.Hint, len(hints))
	for i, h := range hints {
		out[i] = search.Hint{Pos: h.Pos, Car: h.Car, Inverted: h.Inverted}
	}
	return out
}

// defaultLang mirrors the "fr" default the other implementations use.
func defaultLang(lang string) string {
	if lang == "" {
		return "fr"
	}
	return lang
}

// ensureSlice guarantees a non-nil slice so JSON encodes [] rather than null.
func ensureSlice(s []string) []string {
	if s == nil {
		return []string{}
	}
	return s
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func handleSearchFile(w http.ResponseWriter, r *http.Request) {
	var req searchFileRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var words []string
	var err error
	if parallelMode {
		words, err = search.InFileSplit(defaultLang(req.Lang), req.NbCar, req.LstCar, toSearchHints(req.LstHint), req.Strict, search.SplitDegree())
	} else {
		words, err = search.InFile(defaultLang(req.Lang), req.NbCar, req.LstCar, toSearchHints(req.LstHint), req.Strict)
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, searchResponse{Words: ensureSlice(words), Count: len(words)})
}

func handleSearchMany(w http.ResponseWriter, r *http.Request) {
	var req searchManyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var words []string
	var err error
	if parallelMode {
		words, err = search.InManyFilesNested(defaultLang(req.Lang), req.Cars, toSearchHints(req.LstHint), search.SplitDegree())
	} else {
		words, err = search.InManyFiles(defaultLang(req.Lang), req.Cars, toSearchHints(req.LstHint))
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, searchResponse{Words: ensureSlice(words), Count: len(words)})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", handleHealth)
	mux.HandleFunc("POST /search/file", handleSearchFile)
	mux.HandleFunc("POST /search/many", handleSearchMany)

	const addr = "0.0.0.0:8003"
	log.Printf("listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
