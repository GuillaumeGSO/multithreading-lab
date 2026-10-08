// Package search implements the brute-force word-search scan.
// It filters word lists by available letters, positional hints, and word length.
package search

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"unicode/utf8"

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

// Hint is a positional constraint on a word. Position is 1-indexed. Letter is
// the expected character; an empty Letter imposes no constraint. When Excluded
// is true the letter must NOT appear at Position.
type Hint struct {
	Position int
	Letter   string
	Excluded bool
}

// entry is one dictionary word with the data the scan needs, computed once when
// the word list is loaded: the accent-free form (for the letter-pool check) and
// its a–z letter counts (for strict mode). The scan itself allocates nothing.
type entry struct {
	word string
	norm string
	freq [26]uint8
}

func newEntry(word string) entry {
	e := entry{word: word, norm: unidecode.Unidecode(word)}
	for _, r := range e.norm {
		if r >= 'a' && r <= 'z' {
			e.freq[r-'a']++
		}
	}
	return e
}

// wordCache holds entry lists keyed by "lang/length". Each key is written once
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

// langPattern accepts only plain directory names under assets/. Anything else
// ("..", "/", an absolute path) would let lang escape the assets directory.
var langPattern = regexp.MustCompile(`^[a-z]{2,8}$`)

// ValidLang reports whether lang is a safe dictionary directory name.
func ValidLang(lang string) bool {
	return langPattern.MatchString(lang)
}

// loadWords returns the word list for (lang, length), reading it from disk on
// the first call and caching it afterwards. A missing file yields an empty list.
// An unsafe lang yields an empty list and is never cached.
func loadWords(lang string, length int) []entry {
	if !ValidLang(lang) {
		return []entry{}
	}
	key := fmt.Sprintf("%s/%d", lang, length)
	if cached, ok := wordCache.Load(key); ok {
		return cached.([]entry)
	}

	words := []entry{}
	path := filepath.Join(assetsRoot(), lang, fmt.Sprintf("%d.txt", length))
	if data, err := os.ReadFile(path); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			if line = strings.TrimSpace(line); line != "" {
				words = append(words, newEntry(line))
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
		if h.Letter != "" {
			return false
		}
	}
	return true
}

// letterPool is a query's available letters, prepared once per search: a
// membership table for the pool check and a–z counts for strict mode.
type letterPool struct {
	empty  bool
	ascii  [utf8.RuneSelf]bool
	other  map[rune]bool
	freq   [26]int
	strict bool
}

// newLetterPool prepares letters for matching. Each element is one character;
// an element of several characters can never match a single letter.
func newLetterPool(letters []string, strict bool) *letterPool {
	p := &letterPool{empty: true, strict: strict}
	for _, l := range letters {
		r, size := utf8.DecodeRuneInString(l)
		if l == "" || size != len(l) {
			continue
		}
		p.empty = false
		if r < utf8.RuneSelf {
			p.ascii[r] = true
		} else {
			if p.other == nil {
				p.other = map[rune]bool{}
			}
			p.other[r] = true
		}
		if r >= 'a' && r <= 'z' {
			p.freq[r-'a']++
		}
	}
	return p
}

// matches reports whether the word can be built from the pool: every letter of
// its accent-free form is in the pool, and in strict mode no a–z letter is
// needed more often than the pool holds it.
func (p *letterPool) matches(e *entry) bool {
	if e.norm == "" || p.empty {
		return false
	}
	for _, r := range e.norm {
		if r < utf8.RuneSelf {
			if !p.ascii[r] {
				return false
			}
		} else if !p.other[r] {
			return false
		}
	}
	if p.strict {
		for i, n := range e.freq {
			if int(n) > p.freq[i] {
				return false
			}
		}
	}
	return true
}

// matchesContent reports whether word can be built from the letter pool. In
// strict mode each letter is consumed at most once. Convenience form of
// letterPool.matches for a single word (the scan prepares both once instead).
func matchesContent(word string, letters []string, strict bool) bool {
	e := newEntry(word)
	return newLetterPool(letters, strict).matches(&e)
}

// runeAt returns the character at 1-indexed position pos, walking the string
// without allocating. ok is false when pos is outside the word.
func runeAt(word string, pos int) (r rune, ok bool) {
	if pos < 1 {
		return 0, false
	}
	i := 0
	for _, c := range word {
		i++
		if i == pos {
			return c, true
		}
	}
	return 0, false
}

// matchesHints reports whether word satisfies every positional hint.
func matchesHints(word string, hints []Hint) bool {
	if word == "" {
		return false
	}
	if noHints(hints) {
		return true
	}
	for _, h := range hints {
		if h.Letter == "" {
			continue
		}
		letter, _ := utf8.DecodeRuneInString(h.Letter)
		c, ok := runeAt(word, h.Position)
		if !ok {
			// A pinned hint outside the word can never match; an excluded
			// hint is trivially satisfied.
			if !h.Excluded {
				return false
			}
			continue
		}
		if h.Excluded == (c == letter) {
			return false
		}
	}
	return true
}

// scanWords filters entries by the letter pool and/or hints, in order. It is
// the single per-word predicate shared by the sequential and parallel search
// paths, so they always agree on which words match and in what order. Only the
// predicates the query needs are evaluated.
func scanWords(words []entry, pool *letterPool, hints []Hint, emptyLetters, emptyHints bool) []string {
	result := []string{}
	for i := range words {
		e := &words[i]
		var ok bool
		switch {
		case emptyHints:
			ok = pool.matches(e)
		case emptyLetters:
			ok = matchesHints(e.word, hints)
		default:
			ok = pool.matches(e) && matchesHints(e.word, hints)
		}
		if ok {
			result = append(result, e.word)
		}
	}
	return result
}

// lengthPlan returns the word lengths to scan (longest-first) and the letter
// pool for InManyFiles* given the available letters and the hints. A pinned
// (non-excluded) hint at position N forces words of length >= N. Returns empty
// slices when no length can satisfy the hints.
func lengthPlan(letters string, hints []Hint) (lengths []int, pool []string) {
	runes := []rune(letters)
	maxLen := len(runes)
	minLen := 1
	for _, h := range hints {
		if h.Letter != "" && !h.Excluded && h.Position > minLen {
			minLen = h.Position
		}
	}
	if maxLen < minLen {
		return nil, nil
	}
	pool = make([]string, maxLen)
	for i, r := range runes {
		pool[i] = string(r)
	}
	for l := maxLen; l >= minLen; l-- {
		lengths = append(lengths, l)
	}
	return lengths, pool
}

// validateFilters errors on an unsafe lang, when length is zero, or when neither
// letters nor hints are set.
func validateFilters(lang string, length int, emptyLetters, emptyHints bool) error {
	if !ValidLang(lang) {
		return fmt.Errorf("invalid lang: %q", lang)
	}
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
	if err := validateFilters(lang, length, emptyLetters, emptyHints); err != nil {
		return nil, err
	}
	return scanWords(loadWords(lang, length), newLetterPool(letters, strict), hints, emptyLetters, emptyHints), nil
}

// InFileSplit is InFile with intra-file parallelism (axis B): the word list is
// split into `threads` contiguous chunks scanned by separate goroutines and
// merged in index order, so the output equals InFile's. threads<=1 runs inline.
func InFileSplit(lang string, length int, letters []string, hints []Hint, strict bool, threads int) ([]string, error) {
	emptyLetters := noLetters(letters)
	emptyHints := noHints(hints)
	if err := validateFilters(lang, length, emptyLetters, emptyHints); err != nil {
		return nil, err
	}
	words := loadWords(lang, length)
	pool := newLetterPool(letters, strict)
	n := threads
	if n < 1 {
		n = 1
	}
	if n > len(words) {
		n = len(words)
	}
	if n <= 1 {
		return scanWords(words, pool, hints, emptyLetters, emptyHints), nil
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
			partials[idx] = scanWords(words[start:end], pool, hints, emptyLetters, emptyHints)
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
func InManyFilesSeq(lang string, letters string, hints []Hint) ([]string, error) {
	lengths, pool := lengthPlan(letters, hints)
	result := []string{}
	for _, length := range lengths {
		if words, err := InFile(lang, length, pool, hints, false); err == nil {
			result = append(result, words...)
		}
	}
	return result, nil
}

// InManyFiles returns words of every length from len(letters) down to the minimum
// length implied by the hints, ordered longest-first. Each length is scanned in
// its own goroutine (axis A — per-length fan-out); results are reassembled in
// length order.
func InManyFiles(lang string, letters string, hints []Hint) ([]string, error) {
	return manyFanOut(lang, letters, hints, func(length int, pool []string) ([]string, error) {
		return InFile(lang, length, pool, hints, false)
	})
}

// InManyFilesNested fans out per length (axis A) AND splits each length's file
// into `threads` chunks (axis B) — i.e. goroutines spawning goroutines. On a
// CPU-bounded box this deliberately oversubscribes; that is the effect under
// study. Output is identical to InManyFiles.
func InManyFilesNested(lang string, letters string, hints []Hint, threads int) ([]string, error) {
	return manyFanOut(lang, letters, hints, func(length int, pool []string) ([]string, error) {
		return InFileSplit(lang, length, pool, hints, false, threads)
	})
}

// manyFanOut runs `scan` for each planned length in its own goroutine and
// reassembles results longest-first.
func manyFanOut(lang, letters string, hints []Hint, scan func(length int, pool []string) ([]string, error)) ([]string, error) {
	lengths, pool := lengthPlan(letters, hints)
	partials := make([][]string, len(lengths))
	var wg sync.WaitGroup
	for idx, length := range lengths {
		wg.Add(1)
		go func(idx, length int) {
			defer wg.Done()
			if words, err := scan(length, pool); err == nil {
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
