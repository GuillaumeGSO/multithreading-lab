package search

import (
	"fmt"
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
		{"no letter", []Hint{{Position: 1}, {Position: 2}}, true},
		{"has letter", []Hint{{Position: 1, Letter: "a"}}, false},
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
		{"empty word", "", []Hint{{Position: 1, Letter: "a"}}, false},
		{"no hints", "bonjour", nil, true},
		{"match", "salut", []Hint{{Position: 1, Letter: "s"}}, true},
		{"no match", "salut", []Hint{{Position: 1, Letter: "a"}}, false},
		{"excluded match rejects", "salut", []Hint{{Position: 1, Letter: "s", Excluded: true}}, false},
		{"excluded no match accepts", "salut", []Hint{{Position: 1, Letter: "a", Excluded: true}}, true},
		{"out of range normal", "mot", []Hint{{Position: 4, Letter: "a"}}, false},
		{"out of range excluded", "mot", []Hint{{Position: 4, Letter: "a", Excluded: true}}, true},
		{"letter none ignored", "bonjour", []Hint{{Position: 1}}, true},
		{"multiple all match", "salut", []Hint{{Position: 1, Letter: "s"}, {Position: 5, Letter: "t"}}, true},
		{"multiple one fails", "salut", []Hint{{Position: 1, Letter: "s"}, {Position: 5, Letter: "x"}}, false},
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
		hints := []Hint{{Position: 1, Letter: "s"}, {Position: 3, Letter: "a"}, {Position: 5, Letter: "e"}}
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
		hints := []Hint{{Position: 1, Letter: "l"}, {Position: 5, Letter: "s"}}
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
		if len(got) != 494 {
			t.Errorf("got %d words, want 494", len(got))
		}
	})

	t.Run("normal hint skips short words", func(t *testing.T) {
		got, err := InManyFiles("fr", "guillaume", []Hint{{Position: 4, Letter: "a"}})
		if err != nil {
			t.Fatal(err)
		}
		for _, w := range got {
			if len([]rune(w)) < 4 {
				t.Errorf("word %q is shorter than 4 runes", w)
			}
		}
	})

	t.Run("excluded hint includes short words", func(t *testing.T) {
		got, err := InManyFiles("fr", "guillaume", []Hint{{Position: 4, Letter: "z", Excluded: true}})
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

// TestParallelMatchesBaseline guards that the threaded variants return
// byte-identical output (same words, same order) as the sequential baseline,
// for every split degree — so correctness never depends on thread timing.
func TestParallelMatchesBaseline(t *testing.T) {
	letters := []string{"e", "l", "i", "s", "a"}
	fileCases := []struct {
		name       string
		wordLength int
		letters    []string
		hints      []Hint
		strict     bool
	}{
		{"strict letters", 5, letters, nil, true},
		{"open letters", 5, letters, nil, false},
		{"hints only", 5, nil, []Hint{{Position: 1, Letter: "s"}, {Position: 3, Letter: "a"}, {Position: 5, Letter: "e"}}, false},
		{"missing file", 99, []string{"a", "b", "c"}, nil, false},
	}
	for _, c := range fileCases {
		for _, threads := range []int{1, 2, 3, 5} {
			t.Run(fmt.Sprintf("file/%s/t%d", c.name, threads), func(t *testing.T) {
				want, err := InFile("fr", c.wordLength, c.letters, c.hints, c.strict)
				if err != nil {
					t.Fatal(err)
				}
				got, err := InFileSplit("fr", c.wordLength, c.letters, c.hints, c.strict, threads)
				if err != nil {
					t.Fatal(err)
				}
				if !slices.Equal(got, want) {
					t.Errorf("InFileSplit(threads=%d) != InFile\n got=%v\nwant=%v", threads, got, want)
				}
			})
		}
	}

	manyCases := []struct {
		name    string
		letters string
		hints   []Hint
	}{
		{"all lengths", "guillaume", nil},
		{"with hints", "guillaume", []Hint{{Position: 4, Letter: "a"}, {Position: 1, Letter: "a", Excluded: true}}},
	}
	for _, c := range manyCases {
		want, err := InManyFilesSeq("fr", c.letters, c.hints)
		if err != nil {
			t.Fatal(err)
		}
		t.Run("many/fanout/"+c.name, func(t *testing.T) {
			got, err := InManyFiles("fr", c.letters, c.hints)
			if err != nil {
				t.Fatal(err)
			}
			if !slices.Equal(got, want) {
				t.Errorf("InManyFiles != InManyFilesSeq for %s", c.name)
			}
		})
		for _, threads := range []int{1, 2, 3} {
			t.Run(fmt.Sprintf("many/nested/%s/t%d", c.name, threads), func(t *testing.T) {
				got, err := InManyFilesNested("fr", c.letters, c.hints, threads)
				if err != nil {
					t.Fatal(err)
				}
				if !slices.Equal(got, want) {
					t.Errorf("InManyFilesNested(threads=%d) != InManyFilesSeq for %s", threads, c.name)
				}
			})
		}
	}
}

// A hint position below 1 is out of range (never a panic), in every scan path.
func TestNonPositivePositionDoesNotPanic(t *testing.T) {
	for _, pos := range []int{0, -1} {
		hints := []Hint{{Position: pos, Letter: "a"}}
		if got := matchesHints("abc", hints); got {
			t.Errorf("matchesHints(position %d) = true, want false", pos)
		}
		excluded := []Hint{{Position: pos, Letter: "a", Excluded: true}}
		if got := matchesHints("abc", excluded); !got {
			t.Errorf("matchesHints(excluded position %d) = false, want true", pos)
		}
		if _, err := InFileSplit("fr", 5, []string{"a"}, hints, false, 2); err != nil {
			t.Fatal(err)
		}
		if _, err := InManyFilesNested("fr", "abc", hints, 2); err != nil {
			t.Fatal(err)
		}
	}
}

func TestUnsafeLangIsRejected(t *testing.T) {
	for _, lang := range []string{"../../etc", "/etc", "fr/../en", ""} {
		if _, err := InFile(lang, 5, []string{"a"}, nil, false); err == nil {
			t.Errorf("InFile(lang %q) = nil error, want error", lang)
		}
		if words := loadWords(lang, 5); len(words) != 0 {
			t.Errorf("loadWords(%q) returned %d words", lang, len(words))
		}
	}
}
