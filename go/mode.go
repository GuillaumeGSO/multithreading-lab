package main

import (
	"fmt"
	"sort"
	"strings"

	"multithreading-lab/go/search"
)

// searchMode is the implementation the live API serves, chosen by SEARCH_MODE.
// Every language in this lab gives the modes the same meaning:
//
//	baseline  single-threaded scan (/many scans the lengths one after another)
//	parallel  scan split into SPLIT_DEGREE chunks per file; /many also fans out
//	          one goroutine per length (the default)
//
// This implementation has no positional index, so "indexed" is not available.
type searchMode struct {
	name string
	file func(lang string, length int, letters []string, hints []search.Hint, strict bool) ([]string, error)
	many func(lang, letters string, hints []search.Hint) ([]string, error)
}

const defaultMode = "parallel"

var modes = map[string]searchMode{
	"baseline": {
		name: "baseline",
		file: search.InFile,
		many: search.InManyFilesSeq,
	},
	"parallel": {
		name: "parallel",
		file: func(lang string, length int, letters []string, hints []search.Hint, strict bool) ([]string, error) {
			return search.InFileSplit(lang, length, letters, hints, strict, search.SplitDegree())
		},
		many: func(lang, letters string, hints []search.Hint) ([]string, error) {
			return search.InManyFilesNested(lang, letters, hints, search.SplitDegree())
		},
	},
}

// resolveMode returns the mode named by value (empty means the default). An
// unknown name is an error, so a typo fails at startup instead of silently
// serving a different mode.
func resolveMode(value string) (searchMode, error) {
	name := strings.ToLower(strings.TrimSpace(value))
	if name == "" {
		name = defaultMode
	}
	if m, ok := modes[name]; ok {
		return m, nil
	}
	names := make([]string, 0, len(modes))
	for n := range modes {
		names = append(names, n)
	}
	sort.Strings(names)
	return searchMode{}, fmt.Errorf("unknown SEARCH_MODE %q; expected one of %s", name, strings.Join(names, ", "))
}

// mode is the active mode; main replaces it with the resolved SEARCH_MODE.
var mode = modes[defaultMode]
