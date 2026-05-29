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

# Main server executable
add_executable(search src/main.cpp src/search.cpp)
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
