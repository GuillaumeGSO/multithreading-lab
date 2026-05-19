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

bool noLetters(const std::vector<std::string>& letters);
bool noHints(const std::vector<Hint>& hints);

// matchesContent checks whether word can be built from the letter pool. In
// strict mode each letter is consumed at most once. letters is taken by value
// because strict mode mutates it (mirrors Go's slices.Clone per word).
bool matchesContent(const std::string& word,
                    std::vector<std::string> letters,
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
// minimum length implied by hints, ordered longest-first. Each length is
// scanned in its own std::thread (the concurrency model under test).
std::vector<std::string> inManyFiles(const std::string& lang,
                                     const std::string& cars,
                                     const std::vector<Hint>& hints);
