#include "search.h"

#include <algorithm>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <fstream>
#include <future>
#include <mutex>
#include <queue>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

// ---------------------------------------------------------------------------
// Bounded thread pool — shared across all inManyFiles calls so total OS
// threads stay fixed regardless of request concurrency.
// ---------------------------------------------------------------------------
namespace {
class SearchPool {
public:
    explicit SearchPool(int n) {
        for (int i = 0; i < n; i++)
            workers_.emplace_back([this] { run(); });
    }
    ~SearchPool() {
        { std::lock_guard<std::mutex> l(mu_); stop_ = true; }
        cv_.notify_all();
        for (auto& w : workers_) w.join();
    }
    std::future<void> post(std::function<void()> f) {
        auto p = std::make_shared<std::packaged_task<void()>>(std::move(f));
        auto fut = p->get_future();
        { std::lock_guard<std::mutex> l(mu_); q_.push([p] { (*p)(); }); }
        cv_.notify_one();
        return fut;
    }
private:
    void run() {
        for (;;) {
            std::function<void()> task;
            {
                std::unique_lock<std::mutex> l(mu_);
                cv_.wait(l, [this] { return stop_ || !q_.empty(); });
                if (stop_ && q_.empty()) return;
                task = std::move(q_.front());
                q_.pop();
            }
            task();
        }
    }
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> q_;
    std::mutex mu_;
    std::condition_variable cv_;
    bool stop_ = false;
};

// 4 workers: enough parallelism per request without thread explosion under load.
static SearchPool search_pool(std::max(4, static_cast<int>(std::thread::hardware_concurrency()) * 2));
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
                    std::vector<std::string> letters,
                    bool strict) {
    if (word.empty() || noLetters(letters)) return false;
    std::string decoded = unidecode(word);
    // decoded is now ASCII; iterate byte-by-byte (all chars are single-byte).
    // Use a lambda predicate to avoid constructing a std::string per character.
    for (char ch : decoded) {
        auto it = std::find_if(letters.begin(), letters.end(),
            [ch](const std::string& s) { return s.size() == 1 && s[0] == ch; });
        if (it == letters.end()) return false;
        if (strict) letters.erase(it);
    }
    return true;
}

bool matchesHints(const std::string& word, const std::vector<Hint>& hints) {
    if (word.empty()) return false;
    if (noHints(hints)) return true;
    auto runes = utf8Split(word);
    for (const auto& h : hints) {
        if (!h.car || h.car->empty()) continue;
        if (h.pos > static_cast<int>(runes.size())) {
            if (!h.inverted) return false;
            continue;
        }
        bool match = (runes[h.pos - 1] == *h.car);
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

// manyFanOut runs `scan` for each planned length on the shared pool and
// reassembles results longest-first.
static std::vector<std::string> manyFanOut(
    const std::string& cars, const std::vector<Hint>& hints,
    const std::function<std::vector<std::string>(int length, const std::vector<std::string>& letters)>& scan) {
    auto [lengths, letters] = planLengths(cars, hints);
    if (lengths.empty()) return {};

    std::vector<std::vector<std::string>> partials(lengths.size());
    std::vector<std::future<void>> futs;
    futs.reserve(lengths.size());
    for (size_t idx = 0; idx < lengths.size(); idx++) {
        int length = lengths[idx];
        futs.push_back(search_pool.post([&, idx, length]() {
            partials[idx] = scan(length, letters);
        }));
    }
    for (auto& f : futs) f.get();

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
    std::vector<std::thread> ths;
    ths.reserve(n);
    for (int idx = 0; idx < n; idx++) {
        size_t start = std::min(static_cast<size_t>(idx) * chunk, total);
        size_t end = std::min(start + chunk, total);
        ths.emplace_back([&, idx, start, end]() {
            partials[idx] = scanWords(*words, start, end, letters, hints, strict, emptyLetters, emptyHints);
        });
    }
    for (auto& t : ths) t.join();

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
