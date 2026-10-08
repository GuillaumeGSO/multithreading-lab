// HTTP-handler tests: request validation at the API boundary. Every request
// outside the contract's bounds (openapi.yaml) must be a 400 ErrorResponse,
// never a 5xx or a crash.
#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include <doctest.h>

#include "../src/handlers.h"

#include <nlohmann/json.hpp>

#include <cstdlib>
#include <string>
#include <utility>
#include <vector>

using json = nlohmann::json;

struct AssetsFix {
    AssetsFix() {
        if (!std::getenv("ASSETS_ROOT") || !std::getenv("ASSETS_ROOT")[0]) {
            setenv("ASSETS_ROOT", "../../assets", 0);
        }
    }
} assets_fix;

static std::string repeat(const std::string& s, int n) {
    std::string out;
    for (int i = 0; i < n; ++i) out += s;
    return out;
}

static void checkBadRequest(const Reply& r, const std::string& what) {
    INFO(what);
    CHECK(r.status == 400);
    auto body = json::parse(r.body, nullptr, false);
    REQUIRE(body.is_object());
    CHECK(body["error"].is_string());
}

TEST_CASE("invalid /search/file requests are 400") {
    const std::string pin = R"({"position":1,"letter":"a"})";
    std::vector<std::string> bodies = {
        R"({"wordLength":5,"letters":["a"],"hints":[{"position":0,"letter":"a"}]})",
        R"({"wordLength":5,"letters":["a"],"hints":[{"position":32,"letter":"a"}]})",
        R"({"lang":"../../etc","wordLength":5,"letters":["a"]})",
        R"({"lang":"/etc","wordLength":5,"letters":["a"]})",
        R"({"wordLength":0,"letters":["a"]})",
        R"({"wordLength":-1,"letters":["a"]})",
        R"({"wordLength":32,"letters":["a"]})",
        R"({"letters":["a"]})",
        R"({"wordLength":5,"letters":[)" + repeat(R"("a",)", 32) + R"("a"]})",
        R"({"wordLength":5,"hints":[)" + repeat(pin + ",", 31) + pin + "]}",
        R"({"wordLength":5})",
        R"({"wordLength":5.5,"letters":["a"]})",
        R"({"wordLength":5,"letters":["a"],"hints":[{"position":1.5,"letter":"a"}]})",
        R"({not json)",
    };
    for (const auto& b : bodies) checkBadRequest(searchFile(b), b.substr(0, 80));
}

TEST_CASE("invalid /search/many requests are 400") {
    const std::string pin = R"({"position":1,"letter":"a"})";
    std::vector<std::string> bodies = {
        R"({"letters":"abc","hints":[{"position":-1,"letter":"a"}]})",
        R"({"lang":"xx","letters":"abc"})",
        R"({"letters":")" + repeat("a", 33) + R"("})",
        R"({"hints":[)" + pin + "]}",
        R"({"letters":123})",
        R"({not json)",
    };
    for (const auto& b : bodies) checkBadRequest(searchMany(b), b.substr(0, 80));
}

TEST_CASE("valid requests at the bounds are 200") {
    auto file = searchFile(R"({"lang":"fr","wordLength":5,"letters":["e","l","i","s","a"],"hints":[{"position":1,"letter":"s"}]})");
    CHECK(file.status == 200);
    auto body = json::parse(file.body);
    CHECK(body["count"] == body["words"].size());
    CHECK(searchMany(R"({"lang":"en","letters":")" + repeat("a", 32) + R"("})").status == 200);
}
