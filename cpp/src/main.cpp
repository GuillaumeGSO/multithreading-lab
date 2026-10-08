#include "handlers.h"
#include "models.gen.h"  // generated from openapi.yaml (see CMakeLists.txt)

#include <httplib.h>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using json = nlohmann::json;

static void writeJSON(httplib::Response& res, int status, const json& body) {
    res.status = status;
    res.set_content(body.dump(), "application/json");
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
    writeJSON(res, 200, api::HealthResponse{"ok"});
}

// The search endpoints live in handlers.cpp as pure body -> Reply functions.
static void handleSearchFile(const httplib::Request& req, httplib::Response& res) {
    auto reply = searchFile(req.body);
    res.status = reply.status;
    res.set_content(reply.body, "application/json");
}

static void handleSearchMany(const httplib::Request& req, httplib::Response& res) {
    auto reply = searchMany(req.body);
    res.status = reply.status;
    res.set_content(reply.body, "application/json");
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

    // openapi.json is converted from openapi.yaml by the CMake build
    // (build/openapi.json). OPENAPI_JSON_PATH overrides the default, which is
    // the YAML path with a .json extension.
    const char* jsonEnv = std::getenv("OPENAPI_JSON_PATH");
    std::string jsonPath = jsonEnv ? jsonEnv : yamlPath.substr(0, yamlPath.rfind('.')) + ".json";
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
    // 64 KiB is far above any valid request (≤ 32 letters, ≤ 31 hints); larger
    // bodies are refused with 413 before reaching a handler.
    svr.set_payload_max_length(64 * 1024);
    // Errors raised by httplib itself (413 past the payload limit, 404, ...)
    // carry no body; give them the contract's ErrorResponse shape.
    svr.set_error_handler([](const httplib::Request&, httplib::Response& res) {
        if (res.body.empty()) {
            writeJSON(res, res.status, api::ErrorResponse{httplib::status_message(res.status)});
        }
    });
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
