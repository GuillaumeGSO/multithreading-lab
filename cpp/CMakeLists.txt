cmake_minimum_required(VERSION 3.14)
project(search CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

# cpp-httplib — header-only HTTP server/client
FetchContent_Declare(
  httplib
  GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
  GIT_TAG        v0.18.5
)

# nlohmann/json — header-only JSON
FetchContent_Declare(
  json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG        v3.11.3
)

FetchContent_MakeAvailable(httplib json)

# doctest — download single header directly to avoid CMake version compat issues
FetchContent_Declare(
  doctest
  URL      https://raw.githubusercontent.com/doctest/doctest/v2.4.11/doctest/doctest.h
  DOWNLOAD_NO_EXTRACT TRUE
)
FetchContent_MakeAvailable(doctest)

# API models — generated from the repository's openapi.yaml into the build tree
# (never committed). Regenerated whenever the spec or the generator changes.
# Requires Python 3 with PyYAML (the `python3` on PATH is preferred; override
# with -DPython3_EXECUTABLE=/path/to/python3).
set(Python3_FIND_UNVERSIONED_NAMES FIRST)
set(Python3_FIND_FRAMEWORK LAST)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND ${Python3_EXECUTABLE} -c "import yaml"
                RESULT_VARIABLE PYYAML_MISSING OUTPUT_QUIET ERROR_QUIET)
if(PYYAML_MISSING)
  message(FATAL_ERROR "PyYAML is required to generate the API models: "
                      "${Python3_EXECUTABLE} -m pip install pyyaml")
endif()
set(OPENAPI_SPEC ${CMAKE_CURRENT_SOURCE_DIR}/../openapi.yaml CACHE FILEPATH "API contract")
set(MODELS_HEADER ${CMAKE_CURRENT_BINARY_DIR}/generated/models.gen.h)
add_custom_command(
  OUTPUT  ${MODELS_HEADER}
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/codegen/gen_models.py ${OPENAPI_SPEC} ${MODELS_HEADER}
  DEPENDS ${OPENAPI_SPEC} ${CMAKE_CURRENT_SOURCE_DIR}/codegen/gen_models.py
  COMMENT "Generating API models from openapi.yaml"
)
# The same contract as JSON, served at /openapi.json.
set(SPEC_JSON ${CMAKE_CURRENT_BINARY_DIR}/openapi.json)
add_custom_command(
  OUTPUT  ${SPEC_JSON}
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/codegen/spec_to_json.py ${OPENAPI_SPEC} ${SPEC_JSON}
  DEPENDS ${OPENAPI_SPEC} ${CMAKE_CURRENT_SOURCE_DIR}/codegen/spec_to_json.py
  COMMENT "Converting openapi.yaml to openapi.json"
)
add_custom_target(api_models DEPENDS ${MODELS_HEADER} ${SPEC_JSON})

# Main server executable
add_executable(search src/main.cpp src/search.cpp)
add_dependencies(search api_models)
target_include_directories(search PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/generated)
target_link_libraries(search PRIVATE httplib::httplib nlohmann_json::nlohmann_json)
if(UNIX)
  target_link_libraries(search PRIVATE pthread)
endif()

# Benchmark executable (no httplib — runs the algorithm in-process, emits JSON)
add_executable(bench src/bench.cpp src/search.cpp)
target_link_libraries(bench PRIVATE nlohmann_json::nlohmann_json)
if(UNIX)
  target_link_libraries(bench PRIVATE pthread)
endif()

# Test executable (no httplib dependency — pure algorithm tests)
add_executable(test_search test/test_search.cpp src/search.cpp)
target_include_directories(test_search PRIVATE ${doctest_SOURCE_DIR})
target_link_libraries(test_search PRIVATE nlohmann_json::nlohmann_json)
if(UNIX)
  target_link_libraries(test_search PRIVATE pthread)
endif()

enable_testing()
add_test(NAME test_search COMMAND test_search)
