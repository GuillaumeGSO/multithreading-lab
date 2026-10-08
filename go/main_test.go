package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

// TestMain points ASSETS_ROOT at the repo-root assets directory.
func TestMain(m *testing.M) {
	if os.Getenv("ASSETS_ROOT") == "" {
		os.Setenv("ASSETS_ROOT", "../assets")
	}
	os.Exit(m.Run())
}

func post(t *testing.T, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	newMux().ServeHTTP(rec, req)
	return rec
}

// Every request outside the contract's bounds must be a 400 ErrorResponse.
func TestInvalidRequestsAre400(t *testing.T) {
	pin := `{"position":1,"letter":"a"}`
	cases := []struct{ path, body string }{
		{"/search/file", `{"wordLength":5,"letters":["a"],"hints":[{"position":0,"letter":"a"}]}`},
		{"/search/many", `{"letters":"abc","hints":[{"position":-1,"letter":"a"}]}`},
		{"/search/file", `{"wordLength":5,"letters":["a"],"hints":[{"position":32,"letter":"a"}]}`},
		{"/search/file", `{"lang":"../../etc","wordLength":5,"letters":["a"]}`},
		{"/search/file", `{"lang":"/etc","wordLength":5,"letters":["a"]}`},
		{"/search/many", `{"lang":"xx","letters":"abc"}`},
		{"/search/file", `{"wordLength":0,"letters":["a"]}`},
		{"/search/file", `{"wordLength":-1,"letters":["a"]}`},
		{"/search/file", `{"wordLength":32,"letters":["a"]}`},
		{"/search/file", `{"letters":["a"]}`},
		{"/search/file", `{"wordLength":5,"letters":[` + strings.Repeat(`"a",`, 32) + `"a"]}`},
		{"/search/file", `{"wordLength":5,"hints":[` + strings.Repeat(pin+",", 31) + pin + `]}`},
		{"/search/many", `{"letters":"` + strings.Repeat("a", 33) + `"}`},
		{"/search/many", `{"hints":[` + pin + `]}`},
		{"/search/many", `{"letters":123}`},
		{"/search/file", `{"wordLength":5}`},
		{"/search/file", `{not json`},
		{"/search/many", `{not json`},
	}
	for _, c := range cases {
		rec := post(t, c.path, c.body)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("%s %.80s: status %d, want 400 (%s)", c.path, c.body, rec.Code, rec.Body)
			continue
		}
		var body struct{ Error string }
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil || body.Error == "" {
			t.Errorf("%s %.80s: body %q is not an ErrorResponse", c.path, c.body, rec.Body)
		}
	}
}

func TestValidRequestsAtTheBoundsAre200(t *testing.T) {
	ok := []struct{ path, body string }{
		{"/search/file", `{"lang":"fr","wordLength":5,"letters":["e","l","i","s","a"],"hints":[{"position":1,"letter":"s"}]}`},
		{"/search/many", `{"lang":"en","letters":"` + strings.Repeat("a", 32) + `"}`},
	}
	for _, c := range ok {
		if rec := post(t, c.path, c.body); rec.Code != http.StatusOK {
			t.Errorf("%s %s: status %d, want 200 (%s)", c.path, c.body, rec.Code, rec.Body)
		}
	}
}

// /openapi.json is the served openapi.yaml, converted without loss.
func TestOpenAPIJSONMatchesSpec(t *testing.T) {
	if err := loadSpec("../openapi.yaml"); err != nil {
		t.Fatal(err)
	}
	rec := httptest.NewRecorder()
	newMux().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/openapi.json", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	var served map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &served); err != nil {
		t.Fatal(err)
	}
	info, _ := served["info"].(map[string]any)
	paths, _ := served["paths"].(map[string]any)
	if info["version"] != "1.0.0" || paths["/search/many"] == nil {
		t.Errorf("unexpected spec: info=%v, %d paths", info, len(paths))
	}
}

// A body over the 64 KiB cap is a 413 ErrorResponse.
func TestOversizedBodyIs413(t *testing.T) {
	rec := post(t, "/search/many", `{"letters":"`+strings.Repeat("a", 70000)+`"}`)
	if rec.Code != http.StatusRequestEntityTooLarge || !strings.Contains(rec.Body.String(), `"error"`) {
		t.Errorf("status %d, body %s; want 413 ErrorResponse", rec.Code, rec.Body)
	}
}
