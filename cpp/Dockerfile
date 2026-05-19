# Build stage — compile with CMake + FetchContent deps.
FROM alpine:3.20 AS build
RUN apk add --no-cache build-base cmake git
WORKDIR /build
# Copy build definition first so FetchContent downloads are cached between
# source changes (docker layer cache trick).
COPY cpp/CMakeLists.txt .
COPY cpp/src/ src/
COPY cpp/test/ test/
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc)

# Runtime stage — minimal Alpine image with just the binary and word lists.
FROM alpine:3.20
RUN apk add --no-cache libstdc++
WORKDIR /app
COPY --from=build /build/build/search /app/search
COPY assets/ /app/assets/
ENV ASSETS_ROOT=/app/assets
ENV PORT=8004
EXPOSE 8004
CMD ["/app/search"]
