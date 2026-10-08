# Build stage — compile a static binary.
FROM golang:1.26-alpine AS build
WORKDIR /build
COPY go/go.mod go/go.sum ./
RUN go mod download
COPY go/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /search . && \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /bench ./bench

# Runtime stage — minimal scratch image with the binaries and word lists.
FROM scratch
WORKDIR /app
COPY --from=build /search /app/search
COPY --from=build /bench /app/bench
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json
COPY openapi.yaml /app/openapi.yaml
ENV ASSETS_ROOT=/app/assets
# scratch has no user database: run as the conventional "nobody" UID/GID.
USER 65534:65534
EXPOSE 8003
ENTRYPOINT ["/app/search"]
