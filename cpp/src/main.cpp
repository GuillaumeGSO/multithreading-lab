#include "search.h"

#include <httplib.h>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
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

// g_openApiSpec holds the contents of openapi.yaml, loaded once at startup.
static std::string g_openApiSpec;
// g_openApiSpecJson holds the pre-converted JSON version (from openapi.json).
static std::string g_openApiSpecJson;

static const std::string kSwaggerUIHTML = R"html(<!DOCTYPE html>
<html>
<head>
  <title>Word Search API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
<script>
window.onload = function() {
  SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui", presets: [SwaggerUIBundle.presets.apis], layout: "BaseLayout" });
}
</script>
</body>
</html>)html";

// handleOpenApi serves the repo-level openapi.yaml spec.
// The file path is controlled by OPENAPI_PATH (default: /app/openapi.yaml).
static void handleOpenApi(const httplib::Request&, httplib::Response& res) {
    if (g_openApiSpec.empty()) {
        res.status = 503;
        res.set_content("{\"error\":\"OpenAPI spec not loaded\"}", "application/json");
        return;
    }
    res.status = 200;
    res.set_content(g_openApiSpec, "application/yaml");
}

// handleOpenApiJson serves the JSON-encoded OpenAPI spec at /openapi.json.
static void handleOpenApiJson(const httplib::Request&, httplib::Response& res) {
    if (g_openApiSpecJson.empty()) {
        res.status = 503;
        res.set_content("{\"error\":\"OpenAPI spec not loaded\"}", "application/json");
        return;
    }
    res.status = 200;
    res.set_content(g_openApiSpecJson, "application/json");
}

// handleDocs serves an embedded Swagger UI pointing to /openapi.json.
static void handleDocs(const httplib::Request&, httplib::Response& res) {
    res.status = 200;
    res.set_content(kSwaggerUIHTML, "text/html; charset=utf-8");
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
    const char* specPath = std::getenv("OPENAPI_PATH");
    std::string yamlPath = specPath ? specPath : "/app/openapi.yaml";
    std::ifstream specFile(yamlPath);
    if (specFile) {
        std::ostringstream ss;
        ss << specFile.rdbuf();
        g_openApiSpec = ss.str();
    } else {
        std::cerr << "warning: openapi.yaml not found; /openapi.yaml will return 503\n";
    }

    // openapi.json is pre-converted from openapi.yaml at Docker build time.
    std::string jsonPath = yamlPath.substr(0, yamlPath.rfind('.')) + ".json";
    std::ifstream jsonFile(jsonPath);
    if (jsonFile) {
        std::ostringstream ss;
        ss << jsonFile.rdbuf();
        g_openApiSpecJson = ss.str();
    } else {
        std::cerr << "warning: openapi.json not found; /openapi.json will return 503\n";
    }

    int port = 8004;
    if (const char* p = std::getenv("PORT"))
        port = std::stoi(p);

    httplib::Server svr;
    // httplib serves one connection per worker thread and holds that thread for
    // the connection's whole keep-alive lifetime, not just per request. So the
    // pool must be sized for concurrent *connections*, not CPU: under load
    // generators that keep connections alive (Artillery), too few threads means
    // idle-but-open connections occupy every worker and starve new ones — even
    // /health — into socket timeouts. (That is what felled the old fixed pool.)
    // A thread blocked on an idle socket costs almost nothing, so we provision
    // generously and let the search thread budget bound the actual CPU work.
    // A shorter keep-alive timeout frees idle connections promptly as a backstop.
    svr.new_task_queue = [] { return new httplib::ThreadPool(64); };
    svr.set_keep_alive_timeout(2);
    svr.Get("/health",         handleHealth);
    svr.Get("/openapi.yaml",   handleOpenApi);
    svr.Get("/openapi.json",   handleOpenApiJson);
    svr.Get("/docs",           handleDocs);
    svr.Post("/search/file",   handleSearchFile);
    svr.Post("/search/many",   handleSearchMany);

    std::cout << "listening on 0.0.0.0:" << port << std::endl;
    if (!svr.listen("0.0.0.0", port)) {
        std::cerr << "failed to start server on port " << port << std::endl;
        return 1;
    }
    return 0;
}
