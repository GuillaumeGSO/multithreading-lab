// Package search ports the brute-force word-search algorithm from python-base.
// It filters word lists by available letters, positional hints, and word length.
package search

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"sync"

	unidecode "github.com/mozillazg/go-unidecode"
)

// SplitDegree is the number of contiguous chunks a single file is scanned in
// (axis B — intra-file split). SPLIT_DEGREE env, default 2 ("halves").
func SplitDegree() int {
	if v := os.Getenv("SPLIT_DEGREE"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 2
}

// Hint is a positional constraint on a word. Pos is 1-indexed. Car is the
// expected character; a nil or empty Car imposes no constraint. When Inverted
// is true the character must NOT appear at Pos.
type Hint struct {
	Pos      int
	Car      *string
	Inverted bool
}

// wordCache holds word lists keyed by "lang/length". Each key is written once
// and then read by many request goroutines, so sync.Map is a good fit. Stored
// slices are treated as immutable.
var wordCache sync.Map

// assetsRoot resolves the word-list directory, defaulting to a relative path.
func assetsRoot() string {
	if root := os.Getenv("ASSETS_ROOT"); root != "" {
		return root
	}
	return "assets"
}

// loadWords returns the word list for (lang, length), reading it from disk on
// the first call and caching it afterwards. A missing file yields an empty list.
func loadWords(lang string, length int) []string {
	key := fmt.Sprintf("%s/%d", lang, length)
	if cached, ok := wordCache.Load(key); ok {
		return cached.([]string)
	}

	words := []string{}
	path := filepath.Join(assetsRoot(), lang, fmt.Sprintf("%d.txt", length))
	if data, err := os.ReadFile(path); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			if line = strings.TrimSpace(line); line != "" {
				words = append(words, line)
			}
		}
	}

	wordCache.Store(key, words)
	return words
}

// noLetters reports whether the letter pool imposes no constraint.
func noLetters(letters []string) bool {
	for _, c := range letters {
		if c != "" {
			return false
		}
	}
	return true
}

// noHints reports whether the hint list imposes no constraint.
func noHints(hints []Hint) bool {
	for _, h := range hints {
		if h.Car != nil && *h.Car != "" {
			return false
		}
	}
	return true
}

// matchesContent reports whether word can be built from the letter pool. In
// strict mode each letter is consumed at most once. The caller must pass a copy
// of letters, since strict mode mutates the slice.
func matchesContent(word string, letters []string, strict bool) bool {
	if word == "" || noLetters(letters) {
		return false
	}
	for _, r := range unidecode.Unidecode(word) {
		idx := slices.Index(letters, string(r))
		if idx == -1 {
			return false
		}
		if strict {
			letters = slices.Delete(letters, idx, idx+1)
		}
	}
	return true
}

// matchesHints reports whether word satisfies every positional hint.
func matchesHints(word string, hints []Hint) bool {
	if word == "" {
		return false
	}
	if noHints(hints) {
		return true
	}
	runes := []rune(word)
	for _, h := range hints {
		if h.Car == nil || *h.Car == "" {
			continue
		}
		if h.Pos > len(runes) {
			if !h.Inverted {
				return false
			}
			continue
		}
		car := []rune(*h.Car)[0]
		if h.Inverted {
			if runes[h.Pos-1] == car {
				return false
			}
		} else if runes[h.Pos-1] != car {
			return false
		}
	}
	return true
}

// scanWords filters a slice of words by the letter pool and/or hints, in order.
// It is the single per-word predicate shared by the sequential and parallel
// search paths, so they always agree on which words match and in what order.
func scanWords(words, letters []string, hints []Hint, strict, emptyLetters, emptyHints bool) []string {
	result := []string{}
	for _, word := range words {
		// matchesContent mutates its slice in strict mode, so clone per word.
		byContent := matchesContent(word, slices.Clone(letters), strict)
		byHint := matchesHints(word, hints)
		switch {
		case byContent && emptyHints:
			result = append(result, word)
		case emptyLetters && byHint:
			result = append(result, word)
		case byContent && byHint:
			result = append(result, word)
		}
	}
	return result
}

// lengthPlan returns the word lengths to scan (longest-first) and the letter
// pool for InManyFiles* given the available cars and the hints. A normal
// (non-inverted) hint at position N forces words of length >= N. Returns empty
// slices when no length can satisfy the hints.
func lengthPlan(cars string, hints []Hint) (lengths []int, letters []string) {
	carsRunes := []rune(cars)
	maxLen := len(carsRunes)
	minLen := 1
	for _, h := range hints {
		if h.Car != nil && *h.Car != "" && !h.Inverted && h.Pos > minLen {
			minLen = h.Pos
		}
	}
	if maxLen < minLen {
		return nil, nil
	}
	letters = make([]string, maxLen)
	for i, r := range carsRunes {
		letters[i] = string(r)
	}
	for l := maxLen; l >= minLen; l-- {
		lengths = append(lengths, l)
	}
	return lengths, letters
}

// validateFilters errors when length is zero or neither letters nor hints are set.
func validateFilters(length int, emptyLetters, emptyHints bool) error {
	if length == 0 || (emptyLetters && emptyHints) {
		return errors.New("letters and hints cannot both be empty")
	}
	return nil
}

// InFile returns words of exactly length runes matching the letter pool and/or
// the positional hints. It errors when length is zero or when neither a letter
// pool nor a hint is provided. (Baseline — single-threaded.)
func InFile(lang string, length int, letters []string, hints []Hint, strict bool) ([]string, error) {
	emptyLetters := noLetters(letters)
	emptyHints := noHints(hints)
	if err := validateFilters(length, emptyLetters, emptyHints); err != nil {
		return nil, err
	}
	return scanWords(loadWords(lang, length), letters, hints, strict, emptyLetters, emptyHints), nil
}

// InFileSplit is InFile with intra-file parallelism (axis B): the word list is
// split into `threads` contiguous chunks scanned by separate goroutines and
// merged in index order, so the output equals InFile's. threads<=1 runs inline.
func InFileSplit(lang string, length int, letters []string, hints []Hint, strict bool, threads int) ([]string, error) {
	emptyLetters := noLetters(letters)
	emptyHints := noHints(hints)
	if err := validateFilters(length, emptyLetters, emptyHints); err != nil {
		return nil, err
	}
	words := loadWords(lang, length)
	n := threads
	if n < 1 {
		n = 1
	}
	if n > len(words) {
		n = len(words)
	}
	if n <= 1 {
		return scanWords(words, letters, hints, strict, emptyLetters, emptyHints), nil
	}

	chunk := (len(words) + n - 1) / n // ceil keeps chunks contiguous
	partials := make([][]string, n)
	var wg sync.WaitGroup
	for idx := 0; idx < n; idx++ {
		start := idx * chunk
		end := start + chunk
		if start > len(words) {
			start = len(words)
		}
		if end > len(words) {
			end = len(words)
		}
		wg.Add(1)
		go func(idx, start, end int) {
			defer wg.Done()
			partials[idx] = scanWords(words[start:end], letters, hints, strict, emptyLetters, emptyHints)
		}(idx, start, end)
	}
	wg.Wait()

	result := []string{}
	for _, p := range partials {
		result = append(result, p...)
	}
	return result, nil
}

// InManyFilesSeq scans every length sequentially (baseline — no concurrency).
func InManyFilesSeq(lang string, cars string, hints []Hint) ([]string, error) {
	lengths, letters := lengthPlan(cars, hints)
	result := []string{}
	for _, length := range lengths {
		if words, err := InFile(lang, length, letters, hints, false); err == nil {
			result = append(result, words...)
		}
	}
	return result, nil
}

// InManyFiles returns words of every length from len(cars) down to the minimum
// length implied by the hints, ordered longest-first. Each length is scanned in
// its own goroutine (axis A — per-length fan-out); results are reassembled in
// length order.
func InManyFiles(lang string, cars string, hints []Hint) ([]string, error) {
	return manyFanOut(lang, cars, hints, func(length int, letters []string) ([]string, error) {
		return InFile(lang, length, letters, hints, false)
	})
}

// InManyFilesNested fans out per length (axis A) AND splits each length's file
// into `threads` chunks (axis B) — i.e. goroutines spawning goroutines. On a
// CPU-bounded box this deliberately oversubscribes; that is the effect under
// study. Output is identical to InManyFiles.
func InManyFilesNested(lang string, cars string, hints []Hint, threads int) ([]string, error) {
	return manyFanOut(lang, cars, hints, func(length int, letters []string) ([]string, error) {
		return InFileSplit(lang, length, letters, hints, false, threads)
	})
}

// manyFanOut runs `scan` for each planned length in its own goroutine and
// reassembles results longest-first.
func manyFanOut(lang, cars string, hints []Hint, scan func(length int, letters []string) ([]string, error)) ([]string, error) {
	lengths, letters := lengthPlan(cars, hints)
	partials := make([][]string, len(lengths))
	var wg sync.WaitGroup
	for idx, length := range lengths {
		wg.Add(1)
		go func(idx, length int) {
			defer wg.Done()
			if words, err := scan(length, letters); err == nil {
				partials[idx] = words
			}
		}(idx, length)
	}
	wg.Wait()

	result := []string{}
	for _, p := range partials {
		result = append(result, p...)
	}
	return result, nil
}
