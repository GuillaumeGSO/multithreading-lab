# Build stage — compile with CMake + FetchContent deps. The repo layout is
# mirrored (/build/openapi.yaml + /build/cpp) so CMake's ../openapi.yaml
# resolves; Python 3 + PyYAML run the model generator (cpp/codegen).
FROM alpine:3.20 AS build
RUN apk add --no-cache build-base cmake git python3 py3-yaml
WORKDIR /build/cpp
COPY openapi.yaml /build/openapi.yaml
# Copy build definition first so FetchContent downloads are cached between
# source changes (docker layer cache trick).
COPY cpp/CMakeLists.txt .
COPY cpp/codegen/ codegen/
COPY cpp/src/ src/
COPY cpp/test/ test/
# The build also writes build/openapi.json, served at /openapi.json.
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc)

# Runtime stage — minimal Alpine image with just the binary and word lists.
FROM alpine:3.20
RUN apk add --no-cache libstdc++
WORKDIR /app
COPY --from=build /build/cpp/build/search /app/search
COPY --from=build /build/cpp/build/bench /app/bench
COPY --from=build /build/cpp/build/openapi.json /app/openapi.json
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json
COPY openapi.yaml /app/openapi.yaml
ENV ASSETS_ROOT=/app/assets
ENV PORT=8004
EXPOSE 8004
CMD ["/app/search"]
