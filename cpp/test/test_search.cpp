#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include <doctest.h>

#include "../src/search.h"

#include <algorithm>
#include <cstdlib>
#include <string>
#include <vector>

// Set ASSETS_ROOT before any test runs so loadWords finds the real word lists.
// The executable is run from the build directory; adjust the relative path as
// needed, or set ASSETS_ROOT in the environment before running.
struct AssetsFix {
    AssetsFix() {
        // If not already set (e.g. by the test runner or Docker), point at
        // the repo assets relative to the build directory.
        if (!std::getenv("ASSETS_ROOT") || !std::getenv("ASSETS_ROOT")[0]) {
#ifdef _WIN32
            _putenv_s("ASSETS_ROOT", "../../assets");
#else
            setenv("ASSETS_ROOT", "../../assets", 0);
#endif
        }
    }
} assets_fix;

// ---------------------------------------------------------------------------
// utf8Split
// ---------------------------------------------------------------------------

TEST_CASE("utf8Split ASCII") {
    auto v = utf8Split("abc");
    CHECK(v.size() == 3);
    CHECK(v[0] == "a");
    CHECK(v[2] == "c");
}

TEST_CASE("utf8Split accented") {
    // "île" = î (U+00EE, 2 bytes) + l + e
    auto v = utf8Split("\xc3\xaele");
    CHECK(v.size() == 3);
    CHECK(v[0] == "\xc3\xae");  // î
    CHECK(v[1] == "l");
    CHECK(v[2] == "e");
}

// ---------------------------------------------------------------------------
// unidecode
// ---------------------------------------------------------------------------

TEST_CASE("unidecode strips French accents") {
    CHECK(unidecode("\xc3\xaele") == "ile");   // île → ile
    CHECK(unidecode("\xc3\xa9l\xc3\xa8ve") == "eleve");  // élève → eleve
    CHECK(unidecode("ailes") == "ailes");
}

// ---------------------------------------------------------------------------
// noLetters / noHints
// ---------------------------------------------------------------------------

TEST_CASE("noLetters") {
    CHECK(noLetters({}));
    CHECK(noLetters({"", ""}));
    CHECK_FALSE(noLetters({"e", "l"}));
}

TEST_CASE("noHints") {
    CHECK(noHints({}));
    Hint h; h.pos = 1; h.inverted = false;   // car = nullopt
    CHECK(noHints({h}));
    h.car = "s";
    CHECK_FALSE(noHints({h}));
}

// ---------------------------------------------------------------------------
// matchesContent
// ---------------------------------------------------------------------------

TEST_CASE("matchesContent: basic match") {
    CHECK(matchesContent("ailes", {"e","l","i","s","a"}, false));
}

TEST_CASE("matchesContent: missing letter") {
    CHECK_FALSE(matchesContent("ailes", {"e","l","i","s","z"}, false));
}

TEST_CASE("matchesContent: strict mode rejects repeated letter") {
    // "elles" needs two 'e'; pool has only one
    CHECK_FALSE(matchesContent("elles", {"e","l","i","s","a"}, true));
}

TEST_CASE("matchesContent: strict mode allows with two copies") {
    CHECK(matchesContent("elles", {"e","l","l","s","e"}, true));
}

TEST_CASE("matchesContent: accent ile") {
    // "île" unidecodes to "ile"; pool must have i, l, e
    CHECK(matchesContent("\xc3\xaele", {"i","l","e"}, false));
}

TEST_CASE("matchesContent: empty word") {
    CHECK_FALSE(matchesContent("", {"e","l"}, false));
}

// ---------------------------------------------------------------------------
// matchesHints
// ---------------------------------------------------------------------------

TEST_CASE("matchesHints: basic match") {
    Hint h; h.pos = 1; h.car = "s"; h.inverted = false;
    CHECK(matchesHints("slave", {h}));
}

TEST_CASE("matchesHints: mismatch") {
    Hint h; h.pos = 1; h.car = "z"; h.inverted = false;
    CHECK_FALSE(matchesHints("slave", {h}));
}

TEST_CASE("matchesHints: inverted match (char not at pos)") {
    Hint h; h.pos = 1; h.car = "z"; h.inverted = true;
    CHECK(matchesHints("slave", {h}));
}

TEST_CASE("matchesHints: inverted rejects char at pos") {
    Hint h; h.pos = 1; h.car = "s"; h.inverted = true;
    CHECK_FALSE(matchesHints("slave", {h}));
}

TEST_CASE("matchesHints: out-of-range normal rejects") {
    Hint h; h.pos = 10; h.car = "s"; h.inverted = false;
    CHECK_FALSE(matchesHints("slave", {h}));
}

TEST_CASE("matchesHints: out-of-range inverted passes") {
    Hint h; h.pos = 10; h.car = "s"; h.inverted = true;
    CHECK(matchesHints("slave", {h}));
}

TEST_CASE("matchesHints: null car skipped") {
    Hint h; h.pos = 1; h.inverted = false;  // car = nullopt
    CHECK(matchesHints("slave", {h}));
}

TEST_CASE("matchesHints: multiple hints all pass") {
    Hint h1; h1.pos = 1; h1.car = "s"; h1.inverted = false;
    Hint h2; h2.pos = 5; h2.car = "e"; h2.inverted = false;
    CHECK(matchesHints("slave", {h1, h2}));
}

TEST_CASE("matchesHints: empty word") {
    Hint h; h.pos = 1; h.car = "s"; h.inverted = false;
    CHECK_FALSE(matchesHints("", {h}));
}

// ---------------------------------------------------------------------------
// inFile — integration tests against real assets
// ---------------------------------------------------------------------------

TEST_CASE("inFile: strict, letters only — 8 results") {
    auto words = inFile("fr", 5, {"e","l","i","s","a"}, {}, true);
    CHECK(words.size() == 8);
    CHECK(std::find(words.begin(), words.end(), "ailes") != words.end());
}

TEST_CASE("inFile: pos hints only — 8 results incl slave") {
    Hint h1; h1.pos = 1; h1.car = "s"; h1.inverted = false;
    Hint h2; h2.pos = 3; h2.car = "a"; h2.inverted = false;
    Hint h3; h3.pos = 5; h3.car = "e"; h3.inverted = false;
    auto words = inFile("fr", 5, {}, {h1, h2, h3}, false);
    CHECK(words.size() == 8);
    CHECK(std::find(words.begin(), words.end(), "slave") != words.end());
}

TEST_CASE("inFile: letters + hints — 11 results") {
    Hint h1; h1.pos = 1; h1.car = "l"; h1.inverted = false;
    Hint h2; h2.pos = 5; h2.car = "s"; h2.inverted = false;
    auto words = inFile("fr", 5, {"e","l","i","s","a"}, {h1, h2}, false);
    CHECK(words.size() == 11);
}

TEST_CASE("inFile: missing file yields empty vector") {
    auto words = inFile("fr", 99, {"e","l","i","s","a"}, {}, false);
    CHECK(words.empty());
}

TEST_CASE("inFile: empty params throw") {
    CHECK_THROWS_AS(inFile("fr", 5, {}, {}, false), std::runtime_error);
}

TEST_CASE("inFile: zero length throws") {
    CHECK_THROWS_AS(inFile("fr", 0, {"e"}, {}, false), std::runtime_error);
}

// ---------------------------------------------------------------------------
// inManyFiles — integration test against real assets
// ---------------------------------------------------------------------------

TEST_CASE("inManyFiles: guillaume — 494 results, longest-first") {
    auto words = inManyFiles("fr", "guillaume", {});
    CHECK(words.size() == 494);
    // Verify longest-first: first word must be length 9 (or <= 9), none
    // before a shorter one should be longer.
    for (size_t i = 1; i < words.size(); i++) {
        auto prev = utf8Split(words[i-1]);
        auto curr = utf8Split(words[i]);
        CHECK(prev.size() >= curr.size());
    }
}

TEST_CASE("inManyFiles: maxLen < minLen returns empty") {
    // hint forces length >= 10, but cars has 3 chars
    Hint h; h.pos = 10; h.car = "a"; h.inverted = false;
    auto words = inManyFiles("fr", "abc", {h});
    CHECK(words.empty());
}

// ---------------------------------------------------------------------------
// Parallel variants must match the baseline byte-for-byte (same order),
// for every split degree — correctness must not depend on thread timing.
// ---------------------------------------------------------------------------

TEST_CASE("inFileSplit matches inFile for all degrees") {
    std::vector<std::string> letters = {"e", "l", "i", "s", "a"};
    Hint s1; s1.pos = 1; s1.car = "s"; Hint a3; a3.pos = 3; a3.car = "a"; Hint e5; e5.pos = 5; e5.car = "e";
    struct Case { int len; std::vector<std::string> letters; std::vector<Hint> hints; bool strict; };
    std::vector<Case> cases = {
        {5, letters, {}, true},
        {5, letters, {}, false},
        {5, {}, {s1, a3, e5}, false},
        {99, {"a", "b", "c"}, {}, false},
    };
    for (auto& c : cases) {
        auto want = inFile("fr", c.len, c.letters, c.hints, c.strict);
        for (int threads : {1, 2, 3, 5}) {
            auto got = inFileSplit("fr", c.len, c.letters, c.hints, c.strict, threads);
            CHECK(got == want);
        }
    }
}

TEST_CASE("inManyFiles/Nested match inManyFilesSeq for all degrees") {
    Hint a4; a4.pos = 4; a4.car = "a"; Hint na1; na1.pos = 1; na1.car = "a"; na1.inverted = true;
    std::vector<std::vector<Hint>> hintSets = { {}, {a4, na1} };
    for (auto& hints : hintSets) {
        auto want = inManyFilesSeq("fr", "guillaume", hints);
        CHECK(inManyFiles("fr", "guillaume", hints) == want);
        for (int threads : {1, 2, 3}) {
            CHECK(inManyFilesNested("fr", "guillaume", hints, threads) == want);
        }
    }
}
