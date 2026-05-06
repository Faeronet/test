FROM golang:1.22-alpine AS build
WORKDIR /src
RUN apk add --no-cache git ca-certificates
COPY go.mod ./
RUN go mod download || true
COPY . .
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/export-packager ./cmd/export-packager

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata && adduser -D -u 1000 app
COPY --from=build /out/export-packager /usr/local/bin/export-packager
USER app
ENTRYPOINT ["/usr/local/bin/export-packager"]
