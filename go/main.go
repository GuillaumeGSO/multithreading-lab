// Command search exposes the brute-force word-search API over HTTP on :8003.
// The request/response types and routing come from the api package, generated
// from the repository's openapi.yaml.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
	"unicode/utf8"

	"multithreading-lab/go/api"
	"multithreading-lab/go/search"

	"gopkg.in/yaml.v2"
)

// openAPISpec holds the raw YAML bytes of openapi.yaml, loaded once at startup.
var openAPISpec []byte

// openAPISpecJSON holds the JSON-encoded version of openapi.yaml for /openapi.json.
var openAPISpecJSON []byte

// toSearchHints converts request hints into the search package's Hint type.
func toSearchHints(hints []api.Hint) []search.Hint {
	out := make([]search.Hint, len(hints))
	for i, h := range hints {
		out[i] = search.Hint{Position: h.Position, Letter: h.Letter, Excluded: h.Excluded}
	}
	return out
}

// defaultLang applies the spec's default language ("fr") when lang is absent.
func defaultLang(lang api.Lang) string {
	if lang == "" {
		return string(api.Fr)
	}
	return string(lang)
}

// Bounds from openapi.yaml. oapi-codegen generates the types but not runtime
// validation, so the handlers enforce the contract's limits explicitly.
const (
	maxBodyBytes  = 64 << 10 // far above any valid request (≤ 32 letters, ≤ 31 hints)
	minWordLength = 1
	maxWordLength = 31
	maxLetters    = 32
	maxHints      = 31
	minPosition   = 1
	maxPosition   = 31
)

// errBadRequest marks a request rejected by validation (answered with 400).
var errBadRequest = errors.New("bad request")

func badRequest(format string, args ...any) error {
	return fmt.Errorf("%w: %s", errBadRequest, fmt.Sprintf(format, args...))
}

// decodeBody reads a size-capped JSON body into v and reports which top-level
// keys were present, so required fields can be told apart from zero values.
func decodeBody(w http.ResponseWriter, r *http.Request, v any) (map[string]json.RawMessage, error) {
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxBodyBytes))
	if err != nil {
		return nil, badRequest("request body too large or unreadable")
	}
	var keys map[string]json.RawMessage
	if json.Unmarshal(body, &keys) != nil || json.Unmarshal(body, v) != nil {
		return nil, badRequest("malformed JSON body")
	}
	return keys, nil
}

func validateLang(lang api.Lang) error {
	if lang != "" && !lang.Valid() {
		return badRequest("lang: must be one of fr, en")
	}
	return nil
}

func validateHints(hints []api.Hint) error {
	if len(hints) > maxHints {
		return badRequest("hints: at most %d items", maxHints)
	}
	for i, h := range hints {
		if h.Position < minPosition || h.Position > maxPosition {
			return badRequest("hints[%d].position: must be between %d and %d", i, minPosition, maxPosition)
		}
	}
	return nil
}

func validateFileRequest(req api.SearchFileRequest, keys map[string]json.RawMessage) error {
	if _, ok := keys["wordLength"]; !ok {
		return badRequest("wordLength: required")
	}
	if err := validateLang(req.Lang); err != nil {
		return err
	}
	if req.WordLength < minWordLength || req.WordLength > maxWordLength {
		return badRequest("wordLength: must be between %d and %d", minWordLength, maxWordLength)
	}
	if len(req.Letters) > maxLetters {
		return badRequest("letters: at most %d items", maxLetters)
	}
	return validateHints(req.Hints)
}

func validateManyRequest(req api.SearchManyRequest, keys map[string]json.RawMessage) error {
	if _, ok := keys["letters"]; !ok {
		return badRequest("letters: required")
	}
	if err := validateLang(req.Lang); err != nil {
		return err
	}
	if utf8.RuneCountInString(req.Letters) > maxLetters {
		return badRequest("letters: at most %d characters", maxLetters)
	}
	return validateHints(req.Hints)
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
	writeJSON(w, status, api.ErrorResponse{Error: msg})
}

// server implements api.ServerInterface, the handler set generated from openapi.yaml.
type server struct{}

var _ api.ServerInterface = server{}

func (server) Health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, api.HealthResponse{Status: "ok"})
}

// convertYAMLValue recursively converts yaml.v2's map[interface{}]interface{}
// to map[string]interface{} so encoding/json can marshal it.
func convertYAMLValue(v interface{}) interface{} {
	switch val := v.(type) {
	case map[interface{}]interface{}:
		out := make(map[string]interface{}, len(val))
		for k, vv := range val {
			out[fmt.Sprint(k)] = convertYAMLValue(vv)
		}
		return out
	case []interface{}:
		for i, item := range val {
			val[i] = convertYAMLValue(item)
		}
		return val
	default:
		return v
	}
}

// handleOpenAPISpec serves the repo-level openapi.yaml spec.
// The file path is controlled by OPENAPI_PATH (default: /app/openapi.yaml).
func handleOpenAPISpec(w http.ResponseWriter, _ *http.Request) {
	if openAPISpec == nil {
		http.Error(w, `{"error":"OpenAPI spec not loaded"}`, http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/yaml")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(openAPISpec)
}

// handleOpenAPISpecJSON serves the OpenAPI spec as JSON at /openapi.json.
func handleOpenAPISpecJSON(w http.ResponseWriter, _ *http.Request) {
	if openAPISpecJSON == nil {
		http.Error(w, `{"error":"OpenAPI spec not loaded"}`, http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(openAPISpecJSON)
}

const swaggerUIHTML = `<!DOCTYPE html>
<html>
<head>
  <title>Word Search API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
<script>
window.onload = function() {
  SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui", presets: [SwaggerUIBundle.presets.apis], layout: "BaseLayout" });
}
</script>
</body>
</html>`

// handleDocs serves an embedded Swagger UI pointing to /openapi.json.
func handleDocs(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(swaggerUIHTML))
}

func (server) SearchFile(w http.ResponseWriter, r *http.Request) {
	var req api.SearchFileRequest
	keys, err := decodeBody(w, r, &req)
	if err == nil {
		err = validateFileRequest(req, keys)
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	words, err := mode.file(defaultLang(req.Lang), req.WordLength, req.Letters, toSearchHints(req.Hints), req.Strict)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	words = ensureSlice(words)
	writeJSON(w, http.StatusOK, api.SearchResponse{Words: words, Count: len(words)})
}

func (server) SearchMany(w http.ResponseWriter, r *http.Request) {
	var req api.SearchManyRequest
	keys, err := decodeBody(w, r, &req)
	if err == nil {
		err = validateManyRequest(req, keys)
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	words, err := mode.many(defaultLang(req.Lang), req.Letters, toSearchHints(req.Hints))
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	words = ensureSlice(words)
	writeJSON(w, http.StatusOK, api.SearchResponse{Words: words, Count: len(words)})
}

func main() {
	m, err := resolveMode(os.Getenv("SEARCH_MODE"))
	if err != nil {
		log.Fatal(err)
	}
	mode = m
	log.Printf("SEARCH_MODE=%s", mode.name)

	specPath := os.Getenv("OPENAPI_PATH")
	if specPath == "" {
		specPath = "/app/openapi.yaml"
	}
	openAPISpec, err = os.ReadFile(specPath)
	if err != nil {
		log.Printf("warning: could not load openapi.yaml from %s: %v — /openapi.yaml will return 503", specPath, err)
	} else {
		var yamlDoc interface{}
		if yerr := yaml.Unmarshal(openAPISpec, &yamlDoc); yerr == nil {
			openAPISpecJSON, _ = json.Marshal(convertYAMLValue(yamlDoc))
		} else {
			log.Printf("warning: could not parse openapi.yaml as YAML: %v — /openapi.json will return 503", yerr)
		}
	}

	srv := &http.Server{Addr: "0.0.0.0:8003", Handler: newMux()}
	srv.ReadHeaderTimeout = 5 * time.Second
	srv.ReadTimeout = 10 * time.Second
	srv.WriteTimeout = 30 * time.Second
	srv.IdleTimeout = 60 * time.Second

	// Graceful shutdown: stop accepting on SIGINT/SIGTERM (docker stop) and let
	// in-flight requests finish.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdownCtx)
	}()

	log.Printf("listening on %s", srv.Addr)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}

// newMux registers every route: the generated API handlers plus the spec and docs.
func newMux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /openapi.yaml", handleOpenAPISpec)
	mux.HandleFunc("GET /openapi.json", handleOpenAPISpecJSON)
	mux.HandleFunc("GET /docs", handleDocs)
	// Registers GET /health, POST /search/file and POST /search/many.
	api.HandlerFromMux(server{}, mux)
	return mux
}
