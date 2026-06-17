// Command bench runs the word-search algorithm in-process (no HTTP), timing
// each canonical case per concurrency mode with warmup + median-of-N, and
// prints a single JSON report to stdout. Logs go to stderr.
//
// Modes:
//   file cases -> baseline (single thread), split (intra-file SPLIT_DEGREE chunks)
//   many cases -> baseline (sequential), fanout (per-length), nested (per-length + split)
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"multithreading-lab/go/search"
)

type hintJSON struct {
	Pos      int     `json:"pos"`
	Car      *string `json:"car"`
	Inverted bool    `json:"inverted"`
}

type caseJSON struct {
	Name    string     `json:"name"`
	Kind    string     `json:"kind"`
	Lang    string     `json:"lang"`
	NbCar   int        `json:"nb_car"`
	LstCar  []string   `json:"lst_car"`
	Cars    string     `json:"cars"`
	LstHint []hintJSON `json:"lst_hint"`
	Strict  bool       `json:"strict"`
}

type timing struct {
	MedianMs float64 `json:"median_ms"`
	MinMs    float64 `json:"min_ms"`
}

type caseResult struct {
	Name  string            `json:"name"`
	Kind  string            `json:"kind"`
	Count int               `json:"count"`
	Modes map[string]timing `json:"modes"`
}

type report struct {
	Language   string                 `json:"language"`
	Label      string                 `json:"label"`
	Meta       map[string]interface{} `json:"meta"`
	Cases      []caseResult           `json:"cases"`
	Throughput map[string]interface{} `json:"throughput"`
}

// runThroughput runs THROUGHPUT_OPS baseline scans with CONCURRENCY goroutines
// in flight, reporting aggregate ops/sec and median per-op latency under load.
func runThroughput() map[string]interface{} {
	concurrency := envInt("CONCURRENCY", 16)
	ops := envInt("THROUGHPUT_OPS", 200)
	lang, nbCar := "fr", 11
	letters := strings.Split("abcdefghijklmnopqrstuvwxyz", "")
	car := "x"
	hints := []search.Hint{{Pos: 1, Car: &car, Inverted: false}}

	search.InFile(lang, nbCar, letters, hints, false) // warmup

	latencies := make([]float64, ops)
	var count int64
	var idx int64
	var wg sync.WaitGroup
	start := time.Now()
	for w := 0; w < concurrency; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				i := atomic.AddInt64(&idx, 1) - 1
				if i >= int64(ops) {
					return
				}
				t := time.Now()
				r, _ := search.InFile(lang, nbCar, letters, hints, false)
				latencies[i] = float64(time.Since(t).Nanoseconds()) / 1e6
				atomic.StoreInt64(&count, int64(len(r)))
			}
		}()
	}
	wg.Wait()
	elapsed := float64(time.Since(start).Nanoseconds()) / 1e6
	sort.Float64s(latencies)
	return map[string]interface{}{
		"workload":          "file nb_car=11 pool=26 hint=1:x (baseline scan per op)",
		"concurrency":       concurrency,
		"ops":               ops,
		"elapsed_ms":        elapsed,
		"ops_per_sec":       float64(ops) / (elapsed / 1000.0),
		"median_latency_ms": latencies[ops/2],
		"count":             atomic.LoadInt64(&count),
	}
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func toHints(raw []hintJSON) []search.Hint {
	out := make([]search.Hint, len(raw))
	for i, h := range raw {
		out[i] = search.Hint{Pos: h.Pos, Car: h.Car, Inverted: h.Inverted}
	}
	return out
}

// timeMode warms up then times `iters` runs; returns count, median ms, min ms.
func timeMode(fn func() []string, warmup, iters int) (int, timing) {
	count := 0
	for i := 0; i < warmup; i++ {
		count = len(fn())
	}
	samples := make([]float64, iters)
	for i := 0; i < iters; i++ {
		start := time.Now()
		r := fn()
		samples[i] = float64(time.Since(start).Nanoseconds()) / 1e6
		count = len(r)
	}
	sort.Float64s(samples)
	median := samples[len(samples)/2]
	if len(samples)%2 == 0 {
		median = (samples[len(samples)/2-1] + samples[len(samples)/2]) / 2
	}
	return count, timing{MedianMs: median, MinMs: samples[0]}
}

func main() {
	warmup := envInt("BENCH_WARMUP", 20)
	iters := envInt("BENCH_ITERS", 100)
	degree := search.SplitDegree()
	casesPath := os.Getenv("CASES_PATH")
	if casesPath == "" {
		casesPath = "/app/cases.json"
	}

	data, err := os.ReadFile(casesPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read cases:", err)
		os.Exit(1)
	}
	var cases []caseJSON
	if err := json.Unmarshal(data, &cases); err != nil {
		fmt.Fprintln(os.Stderr, "parse cases:", err)
		os.Exit(1)
	}

	var results []caseResult
	for _, c := range cases {
		lang := c.Lang
		if lang == "" {
			lang = "fr"
		}
		hints := toHints(c.LstHint)
		modes := map[string]func() []string{}
		if c.Kind == "file" {
			modes["baseline"] = func() []string {
				r, _ := search.InFile(lang, c.NbCar, c.LstCar, hints, c.Strict)
				return r
			}
			modes["split"] = func() []string {
				r, _ := search.InFileSplit(lang, c.NbCar, c.LstCar, hints, c.Strict, degree)
				return r
			}
		} else {
			modes["baseline"] = func() []string {
				r, _ := search.InManyFilesSeq(lang, c.Cars, hints)
				return r
			}
			modes["fanout"] = func() []string {
				r, _ := search.InManyFiles(lang, c.Cars, hints)
				return r
			}
			modes["nested"] = func() []string {
				r, _ := search.InManyFilesNested(lang, c.Cars, hints, degree)
				return r
			}
		}

		timings := map[string]timing{}
		count := 0
		for name, fn := range modes {
			cnt, t := timeMode(fn, warmup, iters)
			count = cnt
			timings[name] = t
			fmt.Fprintf(os.Stderr, "[Go] %s / %s: %d words, median %.4f ms\n", c.Name, name, cnt, t.MedianMs)
		}
		results = append(results, caseResult{Name: c.Name, Kind: c.Kind, Count: count, Modes: timings})
	}

	throughput := runThroughput()
	fmt.Fprintf(os.Stderr, "[Go] throughput: %.1f ops/s @ concurrency %v\n",
		throughput["ops_per_sec"], throughput["concurrency"])

	rep := report{
		Language:   "go",
		Label:      "Go",
		Meta:       map[string]interface{}{"warmup": warmup, "iterations": iters, "split_degree": degree},
		Cases:      results,
		Throughput: throughput,
	}
	out, _ := json.Marshal(rep)
	fmt.Println(string(out))
}
