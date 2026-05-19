package search

import (
	"os"
	"slices"
	"testing"
)

// TestMain points ASSETS_ROOT at the repo-root assets directory (two levels up
// from go/search/) so the integration tests can read the real word lists.
func TestMain(m *testing.M) {
	if os.Getenv("ASSETS_ROOT") == "" {
		os.Setenv("ASSETS_ROOT", "../../assets")
	}
	os.Exit(m.Run())
}

// ptr returns a pointer to s, for building Hint.Car values inline.
func ptr(s string) *string { return &s }

func TestNoLetters(t *testing.T) {
	cases := []struct {
		name    string
		letters []string
		want    bool
	}{
		{"empty", []string{}, true},
		{"all empty strings", []string{"", ""}, true},
		{"has values", []string{"a", "b"}, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := noLetters(c.letters); got != c.want {
				t.Errorf("noLetters(%v) = %v, want %v", c.letters, got, c.want)
			}
		})
	}
}

func TestNoHints(t *testing.T) {
	cases := []struct {
		name  string
		hints []Hint
		want  bool
	}{
		{"empty", []Hint{}, true},
		{"no car", []Hint{{Pos: 1}, {Pos: 2}}, true},
		{"has car", []Hint{{Pos: 1, Car: ptr("a")}}, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := noHints(c.hints); got != c.want {
				t.Errorf("noHints(%v) = %v, want %v", c.hints, got, c.want)
			}
		})
	}
}

func TestMatchesContent(t *testing.T) {
	cases := []struct {
		name    string
		word    string
		letters []string
		strict  bool
		want    bool
	}{
		{"empty word", "", []string{"a", "b"}, false, false},
		{"empty letters", "abc", []string{}, false, false},
		{"match", "ale", []string{"a", "l", "e", "s"}, false, true},
		{"letter missing", "zoo", []string{"a", "l", "e"}, false, false},
		{"anagram non-strict", "aile", []string{"a", "i", "l", "e"}, false, true},
		{"strict rejects repeated letter", "alle", []string{"a", "l", "e"}, true, false},
		{"accent stripped", "île", []string{"i", "l", "e"}, false, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			// matchesContent mutates its slice in strict mode; pass a copy.
			if got := matchesContent(c.word, slices.Clone(c.letters), c.strict); got != c.want {
				t.Errorf("matchesContent(%q, %v, %v) = %v, want %v", c.word, c.letters, c.strict, got, c.want)
			}
		})
	}
}

func TestMatchesHints(t *testing.T) {
	cases := []struct {
		name  string
		word  string
		hints []Hint
		want  bool
	}{
		{"empty word", "", []Hint{{Pos: 1, Car: ptr("a")}}, false},
		{"no hints", "bonjour", nil, true},
		{"match", "salut", []Hint{{Pos: 1, Car: ptr("s")}}, true},
		{"no match", "salut", []Hint{{Pos: 1, Car: ptr("a")}}, false},
		{"inverted excludes", "salut", []Hint{{Pos: 1, Car: ptr("s"), Inverted: true}}, false},
		{"inverted includes", "salut", []Hint{{Pos: 1, Car: ptr("a"), Inverted: true}}, true},
		{"out of range normal", "mot", []Hint{{Pos: 4, Car: ptr("a")}}, false},
		{"out of range inverted", "mot", []Hint{{Pos: 4, Car: ptr("a"), Inverted: true}}, true},
		{"car none ignored", "bonjour", []Hint{{Pos: 1}}, true},
		{"multiple all match", "salut", []Hint{{Pos: 1, Car: ptr("s")}, {Pos: 5, Car: ptr("t")}}, true},
		{"multiple one fails", "salut", []Hint{{Pos: 1, Car: ptr("s")}, {Pos: 5, Car: ptr("x")}}, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := matchesHints(c.word, c.hints); got != c.want {
				t.Errorf("matchesHints(%q, %v) = %v, want %v", c.word, c.hints, got, c.want)
			}
		})
	}
}

func TestInFile(t *testing.T) {
	t.Run("errors without params", func(t *testing.T) {
		if _, err := InFile("fr", 0, nil, nil, false); err == nil {
			t.Error("expected an error for length 0")
		}
	})

	t.Run("errors with empty letters and hints", func(t *testing.T) {
		if _, err := InFile("fr", 5, nil, nil, false); err == nil {
			t.Error("expected an error for empty filters")
		}
	})

	t.Run("missing file returns empty", func(t *testing.T) {
		got, err := InFile("fr", 99, []string{"a", "b", "c"}, nil, false)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(got) != 0 {
			t.Errorf("got %d words, want 0", len(got))
		}
	})

	t.Run("by content strict", func(t *testing.T) {
		got, err := InFile("fr", 5, []string{"e", "l", "i", "s", "a"}, nil, true)
		if err != nil {
			t.Fatal(err)
		}
		if len(got) != 8 {
			t.Errorf("got %d words, want 8", len(got))
		}
		if !slices.Contains(got, "ailes") {
			t.Errorf(`expected "ailes" in results, got %v`, got)
		}
	})

	t.Run("by hint", func(t *testing.T) {
		hints := []Hint{{Pos: 1, Car: ptr("s")}, {Pos: 3, Car: ptr("a")}, {Pos: 5, Car: ptr("e")}}
		got, err := InFile("fr", 5, nil, hints, false)
		if err != nil {
			t.Fatal(err)
		}
		if len(got) != 8 {
			t.Errorf("got %d words, want 8", len(got))
		}
		if !slices.Contains(got, "slave") {
			t.Errorf(`expected "slave" in results, got %v`, got)
		}
	})

	t.Run("content and hint", func(t *testing.T) {
		hints := []Hint{{Pos: 1, Car: ptr("l")}, {Pos: 5, Car: ptr("s")}}
		got, err := InFile("fr", 5, []string{"e", "l", "i", "s", "a"}, hints, false)
		if err != nil {
			t.Fatal(err)
		}
		if len(got) != 11 {
			t.Errorf("got %d words, want 11", len(got))
		}
	})
}

func TestInManyFiles(t *testing.T) {
	t.Run("all lengths", func(t *testing.T) {
		got, err := InManyFiles("fr", "guillaume", nil)
		if err != nil {
			t.Fatal(err)
		}
		if len(got) != 498 {
			t.Errorf("got %d words, want 498", len(got))
		}
	})

	t.Run("normal hint skips short words", func(t *testing.T) {
		got, err := InManyFiles("fr", "guillaume", []Hint{{Pos: 4, Car: ptr("a")}})
		if err != nil {
			t.Fatal(err)
		}
		for _, w := range got {
			if len([]rune(w)) < 4 {
				t.Errorf("word %q is shorter than 4 runes", w)
			}
		}
	})

	t.Run("inverted hint includes short words", func(t *testing.T) {
		got, err := InManyFiles("fr", "guillaume", []Hint{{Pos: 4, Car: ptr("z"), Inverted: true}})
		if err != nil {
			t.Fatal(err)
		}
		hasShort := false
		for _, w := range got {
			if len([]rune(w)) < 4 {
				hasShort = true
				break
			}
		}
		if !hasShort {
			t.Error("expected at least one word shorter than 4 runes")
		}
	})

	t.Run("results ordered longest-first", func(t *testing.T) {
		got, err := InManyFiles("fr", "guillaume", nil)
		if err != nil {
			t.Fatal(err)
		}
		for i := 1; i < len(got); i++ {
			if len([]rune(got[i])) > len([]rune(got[i-1])) {
				t.Errorf("word %q (index %d) is longer than the previous word %q", got[i], i, got[i-1])
			}
		}
	})
}
