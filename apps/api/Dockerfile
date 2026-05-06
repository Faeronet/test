# Build stage
FROM golang:1.22-alpine AS build
WORKDIR /src

RUN apk add --no-cache git ca-certificates

COPY go.mod ./
RUN go mod download || true

COPY . .
RUN go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/api ./cmd/api

# Runtime stage
FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata && adduser -D -u 1000 app
COPY --from=build /out/api /usr/local/bin/api
USER app
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/api"]
