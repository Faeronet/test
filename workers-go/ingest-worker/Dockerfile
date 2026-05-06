# Build stage
FROM golang:1.22-alpine AS build
WORKDIR /src
RUN apk add --no-cache git ca-certificates
COPY go.mod ./
RUN go mod download || true
COPY . .
RUN go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/ingest-worker ./cmd/ingest-worker

# Runtime stage
FROM alpine:3.20
# tools required for archive extraction and PDF rendering
RUN apk add --no-cache \
        ca-certificates \
        tzdata \
        p7zip \
        poppler-utils \
        && adduser -D -u 1000 app
COPY --from=build /out/ingest-worker /usr/local/bin/ingest-worker
USER app
ENTRYPOINT ["/usr/local/bin/ingest-worker"]
