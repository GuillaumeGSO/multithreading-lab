#include "handlers.h"

#include "models.gen.h"  // generated from openapi.yaml (see CMakeLists.txt)
#include "search.h"

#include <nlohmann/json.hpp>

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using json = nlohmann::json;

namespace {

// parallelMode routes /search through the threaded variants (intra-file split
// for /file, nested per-length fan-out for /many) unless SEARCH_MODE=baseline.
bool parallelMode() {
    const char* m = std::getenv("SEARCH_MODE");
    return !(m && std::string(m) == "baseline");
}

Reply error(int status, const std::string& msg) {
    return {status, json(api::ErrorResponse{msg}).dump()};
}

Reply words(std::vector<std::string> found) {
    api::SearchResponse out;
    out.count = static_cast<int>(found.size());
    out.words = std::move(found);
    return {200, json(out).dump()};
}

// toHints converts the generated api::Hint models into the search Hint type.
std::vector<Hint> toHints(const std::vector<api::Hint>& in) {
    std::vector<Hint> hints;
    hints.reserve(in.size());
    for (const auto& h : in) hints.push_back(Hint{h.position, h.letter, h.excluded});
    return hints;
}

// handle maps failures to the contract's ErrorResponse. Parser messages are not
// echoed: they describe library internals, not the request.
template <typename Fn>
Reply handle(Fn&& fn) {
    try {
        return fn();
    } catch (const json::exception&) {
        return error(400, "malformed JSON body, missing required field or wrong field type");
    } catch (const std::invalid_argument& e) {  // generated validate()
        return error(400, e.what());
    } catch (const SearchError& e) {
        return error(400, e.what());
    } catch (const std::exception& e) {
        std::cerr << "internal error: " << e.what() << std::endl;
        return error(500, "internal error");
    }
}

}  // namespace

Reply searchFile(const std::string& body) {
    return handle([&] {
        auto req = json::parse(body).get<api::SearchFileRequest>();
        api::validate(req);
        auto hints = toHints(req.hints);
        return words(parallelMode()
                         ? inFileSplit(req.lang, req.wordLength, req.letters, hints, req.strict, splitDegree())
                         : inFile(req.lang, req.wordLength, req.letters, hints, req.strict));
    });
}

Reply searchMany(const std::string& body) {
    return handle([&] {
        auto req = json::parse(body).get<api::SearchManyRequest>();
        api::validate(req);
        auto hints = toHints(req.hints);
        return words(parallelMode()
                         ? inManyFilesNested(req.lang, req.letters, hints, splitDegree())
                         : inManyFiles(req.lang, req.letters, hints));
    });
}
