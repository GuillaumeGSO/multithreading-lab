# Build stage — compile a static binary.
FROM golang:1.23-alpine AS build
WORKDIR /build
COPY go/go.mod go/go.sum ./
RUN go mod download
COPY go/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /search .

# Runtime stage — minimal scratch image with just the binary and word lists.
FROM scratch
WORKDIR /app
COPY --from=build /search /app/search
COPY assets/ /app/assets/
ENV ASSETS_ROOT=/app/assets
EXPOSE 8003
ENTRYPOINT ["/app/search"]
