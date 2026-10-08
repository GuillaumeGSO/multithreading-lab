package main

import (
	"slices"
	"testing"

	"multithreading-lab/go/search"
)

// Every mode returns exactly the baseline's words.
func TestModesMatchBaseline(t *testing.T) {
	base := modes["baseline"]
	fileCases := []struct {
		length  int
		letters []string
		hints   []search.Hint
		strict  bool
	}{
		{5, []string{"e", "l", "i", "s", "a"}, nil, true},
		{5, []string{"e", "l", "i", "s", "a"}, []search.Hint{{Position: 1, Letter: "s"}}, false},
		{7, nil, []search.Hint{{Position: 1, Letter: "a"}, {Position: 7, Letter: "e", Excluded: true}}, false},
	}
	manyCases := []struct {
		letters string
		hints   []search.Hint
	}{
		{"guillaume", nil},
		{"artes", []search.Hint{{Position: 1, Letter: "a"}}},
	}
	for name, m := range modes {
		for _, c := range fileCases {
			want, err := base.file("fr", c.length, c.letters, c.hints, c.strict)
			if err != nil || len(want) == 0 {
				t.Fatalf("baseline file %v: %v words, err %v", c, len(want), err)
			}
			got, err := m.file("fr", c.length, c.letters, c.hints, c.strict)
			if err != nil || !slices.Equal(got, want) {
				t.Errorf("%s file %v: got %d words (err %v), want %d", name, c, len(got), err, len(want))
			}
		}
		for _, c := range manyCases {
			want, _ := base.many("fr", c.letters, c.hints)
			got, err := m.many("fr", c.letters, c.hints)
			if err != nil || len(want) == 0 || !slices.Equal(got, want) {
				t.Errorf("%s many %v: got %d words (err %v), want %d", name, c, len(got), err, len(want))
			}
		}
	}
}

func TestResolveMode(t *testing.T) {
	for value, want := range map[string]string{"": "parallel", "baseline": "baseline", " Parallel ": "parallel"} {
		m, err := resolveMode(value)
		if err != nil || m.name != want {
			t.Errorf("resolveMode(%q) = %q, %v; want %q", value, m.name, err, want)
		}
	}
	for _, value := range []string{"indexed", "dispatcher", "fast"} {
		if _, err := resolveMode(value); err == nil {
			t.Errorf("resolveMode(%q) = nil error, want error", value)
		}
	}
}
