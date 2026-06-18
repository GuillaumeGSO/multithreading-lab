#pragma once
#include <memory>
#include <optional>
#include <string>
#include <vector>

// Hint is a positional constraint on a word. pos is 1-indexed. car is the
// expected character; nullopt or empty car imposes no constraint. When inverted
// is true the character must NOT appear at pos.
struct Hint {
    int pos;
    std::optional<std::string> car;
    bool inverted;
};

// utf8Split splits a UTF-8 string into a vector of individual codepoint
// strings. Used for Unicode-safe positional indexing in matchesHints.
std::vector<std::string> utf8Split(const std::string& s);

// unidecode converts a UTF-8 string to ASCII by mapping accented characters to
// their base equivalents (French subset). Mirrors go-unidecode behaviour for
// the French word lists.
std::string unidecode(const std::string& s);

// cpuBudget returns the cores this process may actually use: the cgroup v2 CPU
// quota if present (so it respects Docker's `cpus:` limit rather than the host
// core count), else hardware_concurrency(), overridable via CPU_BUDGET. Sizes
// both the search fan-out and the HTTP server's thread pool.
int cpuBudget();

bool noLetters(const std::vector<std::string>& letters);
bool noHints(const std::vector<Hint>& hints);

// matchesContent checks whether word can be built from the letter pool. In
// strict mode each letter is consumed at most once (tracked with a local bitmap,
// so the hot per-word path copies neither the letter pool nor a decoded string).
bool matchesContent(const std::string& word,
                    const std::vector<std::string>& letters,
                    bool strict);

bool matchesHints(const std::string& word, const std::vector<Hint>& hints);

// loadWords returns a shared_ptr to the cached word list for (lang, length),
// reading from assets/{lang}/{length}.txt on first call. Thread-safe via an
// internal mutex. Returning shared_ptr avoids copying the full word list on
// every call — the Go equivalent returns a slice reference (O(1)).
// A missing file yields an empty vector.
std::shared_ptr<const std::vector<std::string>> loadWords(const std::string& lang, int length);

// inFile returns all words of exactly `length` codepoints that match the
// letter pool and/or positional hints. Throws std::runtime_error when length
// is zero or both letters and hints are empty.
std::vector<std::string> inFile(const std::string& lang,
                                int length,
                                const std::vector<std::string>& letters,
                                const std::vector<Hint>& hints,
                                bool strict);

// inManyFiles returns words across all lengths from len(cars) down to the
// minimum length implied by hints, ordered longest-first. Lengths are scanned
// in parallel up to the global CPU budget (axis A — per-length fan-out, the
// concurrency model under test); excess lengths fold onto the caller.
std::vector<std::string> inManyFiles(const std::string& lang,
                                     const std::string& cars,
                                     const std::vector<Hint>& hints);

// splitDegree is the number of contiguous chunks a single file is scanned in
// (axis B — intra-file split). Reads SPLIT_DEGREE, default 2 ("halves").
int splitDegree();

// inFileSplit is inFile with intra-file parallelism: the word list is split
// into `threads` contiguous chunks scanned in parallel (bounded by the global
// CPU budget) and merged in index order, so output equals inFile's. threads<=1
// runs inline.
std::vector<std::string> inFileSplit(const std::string& lang,
                                     int length,
                                     const std::vector<std::string>& letters,
                                     const std::vector<Hint>& hints,
                                     bool strict,
                                     int threads);

// inManyFilesSeq scans every length sequentially (baseline — no concurrency).
std::vector<std::string> inManyFilesSeq(const std::string& lang,
                                        const std::string& cars,
                                        const std::vector<Hint>& hints);

// inManyFilesNested fans out per length (axis A) AND splits each length's file
// into `threads` chunks (axis B). Both axes draw from the same global CPU
// budget, so nesting can't oversubscribe: once permits run out the inner split
// folds onto its caller. Output is identical to inManyFiles.
std::vector<std::string> inManyFilesNested(const std::string& lang,
                                           const std::string& cars,
                                           const std::vector<Hint>& hints,
                                           int threads);
