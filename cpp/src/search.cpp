#include "search.h"

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <functional>
#include <fstream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

// ---------------------------------------------------------------------------
// Concurrency budget
//
// hardware_concurrency() reports the *host* core count, which ignores the
// container's cgroup CPU quota. Under Docker (`cpus: "2.0"`) it over-counted
// ~5x, so the old host-sized thread pool plus the per-request split threads
// oversubscribed the 2 available cores badly enough to starve the HTTP accept
// loop — even /health timed out under load. We instead size parallelism to the
// real CPU budget and cap the *total* number of concurrent search threads with
// a global permit pool.
// ---------------------------------------------------------------------------

// cpuBudget returns the number of cores this process may actually use: the
// cgroup v2 quota when present, else hardware_concurrency(), overridable via
// the CPU_BUDGET env var (handy for the in-process benchmark). Used both to
// size the search fan-out and to cap the HTTP server's concurrency (main.cpp),
// so concurrent CPU-bound request handling never oversubscribes the cores.
int cpuBudget() {
    if (const char* env = std::getenv("CPU_BUDGET")) {
        try { int n = std::stoi(env); if (n > 0) return n; } catch (...) {}
    }
    // cgroup v2: "<quota> <period>" microseconds, or "max <period>" if unlimited.
    std::ifstream f("/sys/fs/cgroup/cpu.max");
    if (f.is_open()) {
        std::string quota, period;
        if (f >> quota >> period && quota != "max") {
            try {
                long q = std::stol(quota), p = std::stol(period);
                if (q > 0 && p > 0)
                    return std::max(1, static_cast<int>((q + p - 1) / p)); // ceil
            } catch (...) {}
        }
    }
    unsigned hc = std::thread::hardware_concurrency();
    return hc > 0 ? static_cast<int>(hc) : 1;
}

namespace {
// ThreadBudget caps how many search worker threads may run concurrently across
// all requests. A worker grabs a permit before spawning a thread; if none is
// free it folds the work onto the calling thread instead. This bounds total OS
// threads to ~cpuBudget regardless of HTTP concurrency, while a lone request
// (e.g. the benchmark) still gets full fan-out. Acquisition is non-blocking, so
// nested fan-out + split can never deadlock waiting on the budget — the caller
// always makes progress.
class ThreadBudget {
public:
    explicit ThreadBudget(int n) : permits_(n) {}
    bool tryAcquire() {
        int cur = permits_.load(std::memory_order_relaxed);
        while (cur > 0) {
            if (permits_.compare_exchange_weak(cur, cur - 1,
                    std::memory_order_acquire, std::memory_order_relaxed))
                return true;
        }
        return false;
    }
    void release() { permits_.fetch_add(1, std::memory_order_release); }
private:
    std::atomic<int> permits_;
};

// The calling thread is always one worker, so the budget grants permits for the
// *extra* threads: cpuBudget-1 permits → at most cpuBudget concurrent threads.
static ThreadBudget thread_budget(std::max(1, cpuBudget() - 1));

// runParallel splits the index range [0, n) across the caller plus as many
// budget-permitted helper threads as are free, in contiguous slices, and runs
// task(i) for every i. task(i) writes its own result slot, so callers gather in
// index order regardless of how the work was scheduled. All helpers are joined
// before returning.
template <class Task>
void runParallel(size_t n, Task&& task) {
    if (n == 0) return;
    if (n == 1) { task(0); return; }

    size_t extra = 0;
    while (extra + 1 < n && thread_budget.tryAcquire()) extra++;
    size_t workers = extra + 1;            // + the calling thread
    size_t chunk = (n + workers - 1) / workers;

    auto runSlice = [&task, n, chunk](size_t w) {
        size_t start = w * chunk;
        size_t end = std::min(start + chunk, n);
        for (size_t i = start; i < end; i++) task(i);
    };

    std::vector<std::thread> threads;
    threads.reserve(extra);
    for (size_t w = 1; w < workers; w++)
        threads.emplace_back([runSlice, w] { runSlice(w); thread_budget.release(); });
    runSlice(0);
    for (auto& t : threads) t.join();
}
} // namespace

// assetsRoot reads ASSETS_ROOT env var, defaulting to "assets".
static std::string assetsRoot() {
    const char* root = std::getenv("ASSETS_ROOT");
    return (root && root[0]) ? root : "assets";
}

// ---------------------------------------------------------------------------
// UTF-8 helpers
// ---------------------------------------------------------------------------

// Decode a single UTF-8 codepoint starting at s[i]; advance i past it.
static uint32_t decodeCodepoint(const std::string& s, size_t& i) {
    unsigned char c = static_cast<unsigned char>(s[i]);
    uint32_t cp;
    int extra;
    if (c < 0x80) {
        cp = c; extra = 0;
    } else if (c < 0xE0) {
        cp = c & 0x1F; extra = 1;
    } else if (c < 0xF0) {
        cp = c & 0x0F; extra = 2;
    } else {
        cp = c & 0x07; extra = 3;
    }
    i++;
    for (int j = 0; j < extra && i < s.size(); j++, i++) {
        cp = (cp << 6) | (static_cast<unsigned char>(s[i]) & 0x3F);
    }
    return cp;
}

// Encode a codepoint to a UTF-8 string.
static std::string encodeCodepoint(uint32_t cp) {
    std::string out;
    if (cp < 0x80) {
        out += static_cast<char>(cp);
    } else if (cp < 0x800) {
        out += static_cast<char>(0xC0 | (cp >> 6));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    } else if (cp < 0x10000) {
        out += static_cast<char>(0xE0 | (cp >> 12));
        out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    } else {
        out += static_cast<char>(0xF0 | (cp >> 18));
        out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
        out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (cp & 0x3F));
    }
    return out;
}

std::vector<std::string> utf8Split(const std::string& s) {
    std::vector<std::string> result;
    size_t i = 0;
    while (i < s.size()) {
        size_t start = i;
        uint32_t cp = decodeCodepoint(s, i);
        result.push_back(s.substr(start, i - start));
        (void)cp;
    }
    return result;
}

// Unidecode mapping for the French subset.
// Maps Unicode codepoints to their ASCII equivalent string.
static const std::unordered_map<uint32_t, std::string>& unidecodeTable() {
    static const std::unordered_map<uint32_t, std::string> table = {
        // a variants
        {0x00E0, "a"}, {0x00E1, "a"}, {0x00E2, "a"}, {0x00E3, "a"},
        {0x00E4, "a"}, {0x00E5, "a"}, {0x0101, "a"},
        // e variants
        {0x00E8, "e"}, {0x00E9, "e"}, {0x00EA, "e"}, {0x00EB, "e"},
        {0x0113, "e"},
        // i variants
        {0x00EC, "i"}, {0x00ED, "i"}, {0x00EE, "i"}, {0x00EF, "i"},
        {0x012B, "i"},
        // o variants
        {0x00F2, "o"}, {0x00F3, "o"}, {0x00F4, "o"}, {0x00F5, "o"},
        {0x00F6, "o"}, {0x014D, "o"},
        // u variants
        {0x00F9, "u"}, {0x00FA, "u"}, {0x00FB, "u"}, {0x00FC, "u"},
        {0x016B, "u"},
        // y variants
        {0x00FD, "y"}, {0x00FF, "y"},
        // c, n
        {0x00E7, "c"}, {0x00F1, "n"},
        // ligatures
        {0x0153, "oe"}, {0x00E6, "ae"},
        // uppercase variants (in case word lists have them)
        {0x00C0, "a"}, {0x00C1, "a"}, {0x00C2, "a"}, {0x00C3, "a"},
        {0x00C4, "a"}, {0x00C5, "a"},
        {0x00C8, "e"}, {0x00C9, "e"}, {0x00CA, "e"}, {0x00CB, "e"},
        {0x00CC, "i"}, {0x00CD, "i"}, {0x00CE, "i"}, {0x00CF, "i"},
        {0x00D2, "o"}, {0x00D3, "o"}, {0x00D4, "o"}, {0x00D5, "o"},
        {0x00D6, "o"},
        {0x00D9, "u"}, {0x00DA, "u"}, {0x00DB, "u"}, {0x00DC, "u"},
        {0x00C7, "c"}, {0x00D1, "n"},
        {0x0152, "oe"}, {0x00C6, "ae"},
    };
    return table;
}

std::string unidecode(const std::string& s) {
    std::string result;
    const auto& table = unidecodeTable();
    size_t i = 0;
    while (i < s.size()) {
        uint32_t cp = decodeCodepoint(s, i);
        auto it = table.find(cp);
        if (it != table.end()) {
            result += it->second;
        } else if (cp < 0x80) {
            result += static_cast<char>(cp);
        }
        // Non-ASCII codepoints not in the table are dropped (shouldn't happen
        // for French word lists).
    }
    return result;
}

// ---------------------------------------------------------------------------
// Word cache
// ---------------------------------------------------------------------------

static std::mutex cache_mutex;
// Cache stores shared_ptr so callers get a reference-counted handle (O(1))
// rather than a full vector copy (O(n)) on every call. Go returns a slice
// reference; this is the C++ equivalent.
static std::unordered_map<std::string,
                           std::shared_ptr<const std::vector<std::string>>>
    word_cache;

std::shared_ptr<const std::vector<std::string>> loadWords(
    const std::string& lang, int length) {
    std::string key = lang + "/" + std::to_string(length);
    {
        std::lock_guard<std::mutex> lock(cache_mutex);
        auto it = word_cache.find(key);
        if (it != word_cache.end()) return it->second;
    }

    auto words = std::make_shared<std::vector<std::string>>();
    std::string path = assetsRoot() + "/" + lang + "/" +
                       std::to_string(length) + ".txt";
    std::ifstream file(path);
    if (file.is_open()) {
        std::string line;
        while (std::getline(file, line)) {
            // Strip trailing \r (Windows line endings in assets)
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (!line.empty()) words->push_back(line);
        }
    }

    std::lock_guard<std::mutex> lock(cache_mutex);
    // If another thread raced and inserted first, use its entry.
    auto [it, inserted] = word_cache.emplace(key, words);
    return it->second;
}

// ---------------------------------------------------------------------------
// Filter predicates
// ---------------------------------------------------------------------------

bool noLetters(const std::vector<std::string>& letters) {
    for (const auto& c : letters)
        if (!c.empty()) return false;
    return true;
}

bool noHints(const std::vector<Hint>& hints) {
    for (const auto& h : hints)
        if (h.car && !h.car->empty()) return false;
    return true;
}

bool matchesContent(const std::string& word,
                    const std::vector<std::string>& letters,
                    bool strict) {
    if (word.empty() || noLetters(letters)) return false;
    // Hot path: runs on every scanned word. The old version allocated twice per
    // word — a by-value copy of the letter pool plus a unidecoded std::string —
    // which serialised on musl's malloc lock under concurrency and starved the
    // server. Here strict-mode consumption is tracked with a stack-friendly
    // bitmap, and codepoints are decoded and ASCII-folded in place (no string).
    std::vector<char> consumed;
    if (strict) consumed.assign(letters.size(), 0);
    auto take = [&](char ch) -> bool {
        for (size_t k = 0; k < letters.size(); k++) {
            if (strict && consumed[k]) continue;
            const std::string& s = letters[k];
            if (s.size() == 1 && s[0] == ch) {
                if (strict) consumed[k] = 1;
                return true;
            }
        }
        return false;
    };
    const auto& table = unidecodeTable();
    size_t i = 0;
    while (i < word.size()) {
        uint32_t cp = decodeCodepoint(word, i);
        if (cp < 0x80) {
            if (!take(static_cast<char>(cp))) return false;
        } else {
            auto it = table.find(cp);
            if (it != table.end()) {
                for (char ch : it->second)
                    if (!take(ch)) return false;
            }
            // Non-ASCII codepoints absent from the table are dropped, exactly as
            // unidecode() would (shouldn't happen for French word lists).
        }
    }
    return true;
}

bool matchesHints(const std::string& word, const std::vector<Hint>& hints) {
    if (word.empty()) return false;
    if (noHints(hints)) return true;
    for (const auto& h : hints) {
        if (!h.car || h.car->empty()) continue;
        // Locate the h.pos-th codepoint (1-indexed) by decoding in place, with no
        // allocation. matchesHints runs on every scanned word, so the old
        // utf8Split — a heap vector plus a string per codepoint — dominated the
        // hinted-query cost and starved the server under load. We only need the
        // bytes at one position, so walk to it and compare directly.
        size_t i = 0;
        int idx = 0;
        bool inRange = false, match = false;
        while (i < word.size()) {
            size_t start = i;
            decodeCodepoint(word, i);   // advances i past the codepoint
            if (++idx == h.pos) {
                inRange = true;
                match = (word.compare(start, i - start, *h.car) == 0);
                break;
            }
        }
        if (!inRange) {                 // pos beyond the word's length
            if (!h.inverted) return false;
            continue;
        }
        if (h.inverted) {
            if (match) return false;
        } else {
            if (!match) return false;
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// Search entry points
// ---------------------------------------------------------------------------

// scanWords filters words[start, end) by the letter pool and/or hints, in
// order. It is the single per-word predicate shared by the sequential and
// parallel paths, so they always agree on matches and ordering.
static std::vector<std::string> scanWords(const std::vector<std::string>& words,
                                          size_t start, size_t end,
                                          const std::vector<std::string>& letters,
                                          const std::vector<Hint>& hints,
                                          bool strict, bool emptyLetters, bool emptyHints) {
    std::vector<std::string> result;
    for (size_t i = start; i < end; i++) {
        const auto& word = words[i];
        // Pass letters by value so strict mode can mutate per-word copy.
        bool byContent = matchesContent(word, letters, strict);
        bool byHint = matchesHints(word, hints);
        if ((byContent && emptyHints) ||
            (emptyLetters && byHint) ||
            (byContent && byHint)) {
            result.push_back(word);
        }
    }
    return result;
}

// planLengths returns the lengths to scan (longest-first) and the letter pool
// for the inManyFiles* family. Returns an empty length list when no length can
// satisfy the hints.
static std::pair<std::vector<int>, std::vector<std::string>> planLengths(
    const std::string& cars, const std::vector<Hint>& hints) {
    auto carsChars = utf8Split(cars);
    int maxLen = static_cast<int>(carsChars.size());
    int minLen = 1;
    for (const auto& h : hints) {
        if (h.car && !h.car->empty() && !h.inverted && h.pos > minLen)
            minLen = h.pos;
    }
    std::vector<int> lengths;
    if (maxLen >= minLen) {
        for (int l = maxLen; l >= minLen; l--) lengths.push_back(l);
    }
    return {lengths, carsChars};
}

// manyFanOut runs `scan` for each planned length across the thread budget and
// reassembles results longest-first.
static std::vector<std::string> manyFanOut(
    const std::string& cars, const std::vector<Hint>& hints,
    const std::function<std::vector<std::string>(int length, const std::vector<std::string>& letters)>& scan) {
    auto [lengths, letters] = planLengths(cars, hints);
    if (lengths.empty()) return {};

    std::vector<std::vector<std::string>> partials(lengths.size());
    runParallel(lengths.size(), [&](size_t idx) {
        partials[idx] = scan(lengths[idx], letters);
    });

    std::vector<std::string> result;
    for (auto& p : partials) {
        result.insert(result.end(),
                      std::make_move_iterator(p.begin()),
                      std::make_move_iterator(p.end()));
    }
    return result;
}

int splitDegree() {
    const char* v = std::getenv("SPLIT_DEGREE");
    if (v && v[0]) {
        try {
            int n = std::stoi(v);
            if (n > 0) return n;
        } catch (...) {
        }
    }
    return 2;
}

std::vector<std::string> inFile(const std::string& lang,
                                int length,
                                const std::vector<std::string>& letters,
                                const std::vector<Hint>& hints,
                                bool strict) {
    bool emptyLetters = noLetters(letters);
    bool emptyHints = noHints(hints);
    if (length == 0 || (emptyLetters && emptyHints))
        throw std::runtime_error("letters and hints cannot both be empty");

    auto words = loadWords(lang, length);
    return scanWords(*words, 0, words->size(), letters, hints, strict, emptyLetters, emptyHints);
}

std::vector<std::string> inFileSplit(const std::string& lang,
                                     int length,
                                     const std::vector<std::string>& letters,
                                     const std::vector<Hint>& hints,
                                     bool strict,
                                     int threads) {
    bool emptyLetters = noLetters(letters);
    bool emptyHints = noHints(hints);
    if (length == 0 || (emptyLetters && emptyHints))
        throw std::runtime_error("letters and hints cannot both be empty");

    auto words = loadWords(lang, length);
    size_t total = words->size();
    int n = threads < 1 ? 1 : threads;
    if (static_cast<size_t>(n) > total) n = static_cast<int>(total);
    if (n <= 1)
        return scanWords(*words, 0, total, letters, hints, strict, emptyLetters, emptyHints);

    size_t chunk = (total + n - 1) / n; // ceil keeps chunks contiguous
    std::vector<std::vector<std::string>> partials(n);
    runParallel(static_cast<size_t>(n), [&](size_t idx) {
        size_t start = std::min(idx * chunk, total);
        size_t end = std::min(start + chunk, total);
        partials[idx] = scanWords(*words, start, end, letters, hints, strict, emptyLetters, emptyHints);
    });

    std::vector<std::string> result;
    for (auto& p : partials) {
        result.insert(result.end(),
                      std::make_move_iterator(p.begin()),
                      std::make_move_iterator(p.end()));
    }
    return result;
}

std::vector<std::string> inManyFilesSeq(const std::string& lang,
                                        const std::string& cars,
                                        const std::vector<Hint>& hints) {
    auto [lengths, letters] = planLengths(cars, hints);
    std::vector<std::string> result;
    for (int length : lengths) {
        auto w = inFile(lang, length, letters, hints, false);
        result.insert(result.end(),
                      std::make_move_iterator(w.begin()),
                      std::make_move_iterator(w.end()));
    }
    return result;
}

std::vector<std::string> inManyFiles(const std::string& lang,
                                     const std::string& cars,
                                     const std::vector<Hint>& hints) {
    return manyFanOut(cars, hints, [&](int length, const std::vector<std::string>& letters) {
        return inFile(lang, length, letters, hints, false);
    });
}

std::vector<std::string> inManyFilesNested(const std::string& lang,
                                           const std::string& cars,
                                           const std::vector<Hint>& hints,
                                           int threads) {
    return manyFanOut(cars, hints, [&](int length, const std::vector<std::string>& letters) {
        return inFileSplit(lang, length, letters, hints, false, threads);
    });
}
