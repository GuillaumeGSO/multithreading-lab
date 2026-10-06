// Command search exposes the brute-force word-search API over HTTP on :8003.
// The request/response types and routing come from the api package, generated
// from the repository's openapi.yaml.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"multithreading-lab/go/api"
	"multithreading-lab/go/search"

	"gopkg.in/yaml.v2"
)

// parallelMode routes /search through the threaded variants (intra-file split
// for /file, nested per-length fan-out for /many) unless SEARCH_MODE=baseline,
// which restores the original per-endpoint behavior.
var parallelMode = os.Getenv("SEARCH_MODE") != "baseline"

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
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var words []string
	var err error
	if parallelMode {
		words, err = search.InFileSplit(defaultLang(req.Lang), req.WordLength, req.Letters, toSearchHints(req.Hints), req.Strict, search.SplitDegree())
	} else {
		words, err = search.InFile(defaultLang(req.Lang), req.WordLength, req.Letters, toSearchHints(req.Hints), req.Strict)
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	words = ensureSlice(words)
	writeJSON(w, http.StatusOK, api.SearchResponse{Words: words, Count: len(words)})
}

func (server) SearchMany(w http.ResponseWriter, r *http.Request) {
	var req api.SearchManyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var words []string
	var err error
	if parallelMode {
		words, err = search.InManyFilesNested(defaultLang(req.Lang), req.Letters, toSearchHints(req.Hints), search.SplitDegree())
	} else {
		words, err = search.InManyFiles(defaultLang(req.Lang), req.Letters, toSearchHints(req.Hints))
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	words = ensureSlice(words)
	writeJSON(w, http.StatusOK, api.SearchResponse{Words: words, Count: len(words)})
}

func main() {
	specPath := os.Getenv("OPENAPI_PATH")
	if specPath == "" {
		specPath = "/app/openapi.yaml"
	}
	var err error
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

	mux := http.NewServeMux()
	mux.HandleFunc("GET /openapi.yaml", handleOpenAPISpec)
	mux.HandleFunc("GET /openapi.json", handleOpenAPISpecJSON)
	mux.HandleFunc("GET /docs", handleDocs)
	// Registers GET /health, POST /search/file and POST /search/many.
	api.HandlerFromMux(server{}, mux)

	const addr = "0.0.0.0:8003"
	log.Printf("listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
