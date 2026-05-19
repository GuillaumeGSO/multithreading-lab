// Package search ports the brute-force word-search algorithm from python-base.
// It filters word lists by available letters, positional hints, and word length.
package search

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"sync"

	unidecode "github.com/mozillazg/go-unidecode"
)

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

// InFile returns words of exactly length runes matching the letter pool and/or
// the positional hints. It errors when length is zero or when neither a letter
// pool nor a hint is provided.
func InFile(lang string, length int, letters []string, hints []Hint, strict bool) ([]string, error) {
	emptyLetters := noLetters(letters)
	emptyHints := noHints(hints)
	if length == 0 || (emptyLetters && emptyHints) {
		return nil, errors.New("letters and hints cannot both be empty")
	}

	result := []string{}
	for _, word := range loadWords(lang, length) {
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
	return result, nil
}

// InManyFiles returns words of every length from len(cars) down to the minimum
// length implied by the hints, ordered longest-first. Each length is scanned in
// its own goroutine; results are reassembled in length order.
func InManyFiles(lang string, cars string, hints []Hint) ([]string, error) {
	carsRunes := []rune(cars)
	maxLen := len(carsRunes)

	// A normal (non-inverted) hint at position N forces words of length >= N.
	minLen := 1
	for _, h := range hints {
		if h.Car != nil && *h.Car != "" && !h.Inverted && h.Pos > minLen {
			minLen = h.Pos
		}
	}
	if maxLen < minLen {
		return []string{}, nil
	}

	letters := make([]string, maxLen)
	for i, r := range carsRunes {
		letters[i] = string(r)
	}

	// partials[idx] holds the result for one length; idx 0 is the longest.
	// Each goroutine owns its own index, so no locking is needed and the
	// final concatenation stays longest-first.
	count := maxLen - minLen + 1
	partials := make([][]string, count)
	var wg sync.WaitGroup
	for idx := 0; idx < count; idx++ {
		wg.Add(1)
		go func(idx, length int) {
			defer wg.Done()
			// letters is shared read-only — InFile clones it per word internally.
			if words, err := InFile(lang, length, letters, hints, false); err == nil {
				partials[idx] = words
			}
		}(idx, maxLen-idx)
	}
	wg.Wait()

	result := []string{}
	for _, p := range partials {
		result = append(result, p...)
	}
	return result, nil
}
