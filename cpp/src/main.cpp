#include "search.h"

#include <httplib.h>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using json = nlohmann::json;

// parallelMode routes /search through the threaded variants (intra-file split
// for /file, nested per-length fan-out for /many) unless SEARCH_MODE=baseline.
static bool parallelMode() {
    const char* m = std::getenv("SEARCH_MODE");
    return !(m && std::string(m) == "baseline");
}

// defaultLang mirrors the "fr" default every other implementation uses.
static std::string defaultLang(const std::string& lang) {
    return lang.empty() ? "fr" : lang;
}

static void writeJSON(httplib::Response& res, int status, const json& body) {
    res.status = status;
    res.set_content(body.dump(), "application/json");
}

static void writeError(httplib::Response& res, const std::string& msg) {
    writeJSON(res, 400, {{"error", msg}});
}

// toHints converts the JSON hint array into the search::Hint vector.
static std::vector<Hint> toHints(const json& arr) {
    std::vector<Hint> hints;
    for (const auto& h : arr) {
        Hint hint;
        hint.pos = h.value("pos", 0);
        if (h.contains("car") && !h["car"].is_null()) {
            hint.car = h["car"].get<std::string>();
        }
        hint.inverted = h.value("inverted", false);
        hints.push_back(std::move(hint));
    }
    return hints;
}

static void handleHealth(const httplib::Request&, httplib::Response& res) {
    writeJSON(res, 200, {{"status", "ok"}});
}

static void handleSearchFile(const httplib::Request& req,
                              httplib::Response& res) {
    json body;
    try {
        body = json::parse(req.body);
    } catch (const json::exception& e) {
        writeError(res, e.what());
        return;
    }
    try {
        std::string lang = defaultLang(body.value("lang", std::string{}));
        int nbCar = body.value("nb_car", 0);
        std::vector<std::string> lstCar =
            body.value("lst_car", std::vector<std::string>{});
        std::vector<Hint> hints =
            toHints(body.value("lst_hint", json::array()));
        bool strict = body.value("strict", false);

        auto words = parallelMode()
                         ? inFileSplit(lang, nbCar, lstCar, hints, strict, splitDegree())
                         : inFile(lang, nbCar, lstCar, hints, strict);
        writeJSON(res, 200, {{"words", words}, {"count", words.size()}});
    } catch (const std::exception& e) {
        writeError(res, e.what());
    }
}

static void handleSearchMany(const httplib::Request& req,
                              httplib::Response& res) {
    json body;
    try {
        body = json::parse(req.body);
    } catch (const json::exception& e) {
        writeError(res, e.what());
        return;
    }
    try {
        std::string lang = defaultLang(body.value("lang", std::string{}));
        std::string cars = body.value("cars", std::string{});
        std::vector<Hint> hints =
            toHints(body.value("lst_hint", json::array()));

        auto words = parallelMode()
                         ? inManyFilesNested(lang, cars, hints, splitDegree())
                         : inManyFiles(lang, cars, hints);
        writeJSON(res, 200, {{"words", words}, {"count", words.size()}});
    } catch (const std::exception& e) {
        writeError(res, e.what());
    }
}

int main() {
    int port = 8004;
    if (const char* p = std::getenv("PORT"))
        port = std::stoi(p);

    httplib::Server svr;
    svr.new_task_queue = [] { return new httplib::ThreadPool(16); };
    svr.Get("/health",       handleHealth);
    svr.Post("/search/file", handleSearchFile);
    svr.Post("/search/many", handleSearchMany);

    std::cout << "listening on 0.0.0.0:" << port << std::endl;
    if (!svr.listen("0.0.0.0", port)) {
        std::cerr << "failed to start server on port " << port << std::endl;
        return 1;
    }
    return 0;
}
