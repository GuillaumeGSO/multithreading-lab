#pragma once
#include <string>

// Reply is an HTTP status plus a JSON body. The search endpoints are written
// as pure functions of the request body so they can be unit-tested without a
// socket; main.cpp only adapts them to cpp-httplib.
struct Reply {
    int status;
    std::string body;
};

// searchFile / searchMany parse the body into the models generated from
// openapi.yaml, validate it against the contract's bounds, and run the search
// (parallel unless SEARCH_MODE=baseline). Rejected input is a 400
// ErrorResponse; an unexpected failure is a generic 500 ErrorResponse.
Reply searchFile(const std::string& body);
Reply searchMany(const std::string& body);
