// bench runs the word-search algorithm in-process (no HTTP), timing each
// canonical case per concurrency mode with warmup + median-of-N, and prints a
// single JSON report to stdout. Logs go to stderr.
//
// Modes:
//   file cases -> baseline (single thread), split (intra-file SPLIT_DEGREE chunks)
//   many cases -> baseline (sequential), fanout (per-length pool), nested (pool + split)
#include "search.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

using json = nlohmann::json;

static int envInt(const char* key, int def) {
    const char* v = std::getenv(key);
    if (v && v[0]) {
        try {
            return std::stoi(v);
        } catch (...) {
        }
    }
    return def;
}

static std::vector<Hint> toHints(const json& arr) {
    std::vector<Hint> hints;
    for (const auto& h : arr) {
        Hint hint;
        hint.pos = h.value("pos", 0);
        if (h.contains("car") && !h["car"].is_null())
            hint.car = h["car"].get<std::string>();
        hint.inverted = h.value("inverted", false);
        hints.push_back(std::move(hint));
    }
    return hints;
}

struct Timing {
    double median_ms;
    double min_ms;
};

// timeMode warms up then times `iters` runs; returns count + timing.
static Timing timeMode(const std::function<std::vector<std::string>()>& fn,
                       int warmup, int iters, size_t& count) {
    for (int i = 0; i < warmup; i++) count = fn().size();
    std::vector<double> samples;
    samples.reserve(iters);
    for (int i = 0; i < iters; i++) {
        auto start = std::chrono::steady_clock::now();
        auto r = fn();
        auto elapsed = std::chrono::steady_clock::now() - start;
        samples.push_back(std::chrono::duration<double, std::milli>(elapsed).count());
        count = r.size();
    }
    std::sort(samples.begin(), samples.end());
    double median = samples[samples.size() / 2];
    if (samples.size() % 2 == 0)
        median = (samples[samples.size() / 2 - 1] + samples[samples.size() / 2]) / 2.0;
    return {median, samples.front()};
}

// runThroughput runs THROUGHPUT_OPS baseline scans with CONCURRENCY threads in
// flight, reporting aggregate ops/sec and median per-op latency under load.
static json runThroughput() {
    int concurrency = envInt("CONCURRENCY", 16);
    int ops = envInt("THROUGHPUT_OPS", 200);
    std::string lang = "fr";
    int nbCar = 11;
    std::vector<std::string> letters;
    for (char c = 'a'; c <= 'z'; c++) letters.push_back(std::string(1, c));
    Hint h;
    h.pos = 1;
    h.car = "x";
    h.inverted = false;
    std::vector<Hint> hints{h};

    inFile(lang, nbCar, letters, hints, false); // warmup

    std::vector<double> latencies(ops);
    std::atomic<int> idx{0};
    std::atomic<long> count{0};
    auto start = std::chrono::steady_clock::now();
    std::vector<std::thread> workers;
    for (int w = 0; w < concurrency; w++) {
        workers.emplace_back([&]() {
            for (;;) {
                int i = idx.fetch_add(1);
                if (i >= ops) return;
                auto t = std::chrono::steady_clock::now();
                auto r = inFile(lang, nbCar, letters, hints, false);
                latencies[i] = std::chrono::duration<double, std::milli>(
                                   std::chrono::steady_clock::now() - t).count();
                count.store(static_cast<long>(r.size()));
            }
        });
    }
    for (auto& t : workers) t.join();
    double elapsed = std::chrono::duration<double, std::milli>(
                         std::chrono::steady_clock::now() - start).count();
    std::sort(latencies.begin(), latencies.end());
    return json{
        {"workload", "file nb_car=11 pool=26 hint=1:x (baseline scan per op)"},
        {"concurrency", concurrency},
        {"ops", ops},
        {"elapsed_ms", elapsed},
        {"ops_per_sec", ops / (elapsed / 1000.0)},
        {"median_latency_ms", latencies[ops / 2]},
        {"count", count.load()},
    };
}

int main() {
    int warmup = envInt("BENCH_WARMUP", 20);
    int iters = envInt("BENCH_ITERS", 100);
    int degree = splitDegree();
    const char* cp = std::getenv("CASES_PATH");
    std::string casesPath = (cp && cp[0]) ? cp : "/app/cases.json";

    std::ifstream in(casesPath);
    if (!in.is_open()) {
        std::cerr << "cannot open cases: " << casesPath << std::endl;
        return 1;
    }
    json cases;
    in >> cases;

    json outCases = json::array();
    for (const auto& c : cases) {
        std::string name = c.value("name", "");
        std::string kind = c.value("kind", "file");
        std::string lang = c.value("lang", "fr");
        if (lang.empty()) lang = "fr";
        auto hints = toHints(c.value("lst_hint", json::array()));

        std::vector<std::pair<std::string, std::function<std::vector<std::string>()>>> modes;
        if (kind == "file") {
            int nbCar = c.value("nb_car", 0);
            auto letters = c.value("lst_car", std::vector<std::string>{});
            bool strict = c.value("strict", false);
            modes.push_back({"baseline", [=]() { return inFile(lang, nbCar, letters, hints, strict); }});
            modes.push_back({"split", [=]() { return inFileSplit(lang, nbCar, letters, hints, strict, degree); }});
        } else {
            std::string cars = c.value("cars", "");
            modes.push_back({"baseline", [=]() { return inManyFilesSeq(lang, cars, hints); }});
            modes.push_back({"fanout", [=]() { return inManyFiles(lang, cars, hints); }});
            modes.push_back({"nested", [=]() { return inManyFilesNested(lang, cars, hints, degree); }});
        }

        json modeJson = json::object();
        size_t count = 0;
        for (auto& [mname, fn] : modes) {
            size_t c2 = 0;
            Timing t = timeMode(fn, warmup, iters, c2);
            count = c2;
            modeJson[mname] = {{"median_ms", t.median_ms}, {"min_ms", t.min_ms}};
            std::cerr << "[C++] " << name << " / " << mname << ": " << c2
                      << " words, median " << t.median_ms << " ms" << std::endl;
        }
        outCases.push_back({{"name", name}, {"kind", kind}, {"count", count}, {"modes", modeJson}});
    }

    json throughput = runThroughput();
    std::cerr << "[C++] throughput: " << throughput["ops_per_sec"].get<double>()
              << " ops/s @ concurrency " << throughput["concurrency"].get<int>() << std::endl;

    json report = {
        {"language", "cpp"},
        {"label", "C++"},
        {"meta", {{"warmup", warmup}, {"iterations", iters}, {"split_degree", degree}}},
        {"cases", outCases},
        {"throughput", throughput},
    };
    std::cout << report.dump() << std::endl;
    return 0;
}
