// Command search exposes the brute-force word-search API over HTTP on :8003.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

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
	mux.HandleFunc("GET /health", handleHealth)
	mux.HandleFunc("GET /openapi.yaml", handleOpenAPISpec)
	mux.HandleFunc("GET /openapi.json", handleOpenAPISpecJSON)
	mux.HandleFunc("GET /docs", handleDocs)
	mux.HandleFunc("POST /search/file", handleSearchFile)
	mux.HandleFunc("POST /search/many", handleSearchMany)

	const addr = "0.0.0.0:8003"
	log.Printf("listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
