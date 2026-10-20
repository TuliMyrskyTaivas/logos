ARG GOLANG_VERSION=1.27
ARG GOLANGCI_LINT_VERSION=2.15.0

# Lint stage
FROM golang:${GOLANG_VERSION} AS go-lint-stage
ARG GOLANGCI_LINT_VERSION
RUN go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v${GOLANGCI_LINT_VERSION}
WORKDIR /app
# Install Delve
# RUN go install github.com/go-delve/delve/cmd/dlv@latest
# Copy the GolangCI configuration file
COPY golangci-lint.yml /app/.golangci.yml
# Copy the Go module files and download dependencies
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
# Copy the source code into the container
COPY api/ ./api/
COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY pkg/ ./pkg/
# Run linters
RUN golangci-lint run --timeout 5m --config /app/.golangci.yml

# Build stage
FROM golang:${GOLANG_VERSION} AS go-build-stage
WORKDIR /app
COPY --from=go-lint-stage /app /app
COPY --from=go-lint-stage /go/pkg/mod /go/pkg/mod
RUN CGO_ENABLED=0 GOOS=linux go build -o /guldvegt ./cmd/api

# Run the tests in the container
FROM go-lint-stage AS go-test-stage
WORKDIR /app
RUN go test -coverprofile=coverage.out -v ./...

# Assemble a CA bundle that extends the Debian system roots with the Russian
# Ministry of Digital Development (Минцифры) certificates, so the service can
# verify TLS certificates of Russian upstream providers.
FROM debian:trixie-slim AS ca-bundle
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# update-ca-certificates only picks up files with the .crt extension.
COPY certs/*.crt /usr/local/share/ca-certificates/mincifry/
RUN update-ca-certificates

# Deploy the service into a separate lean image
FROM gcr.io/distroless/base-debian13 AS guldvegt-cmd
WORKDIR /
# Replace the distroless CA bundle with the one that also trusts Минцифры roots.
COPY --from=ca-bundle /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=go-build-stage /guldvegt /guldvegt
#COPY --from=go-lint-stage /go/bin/dlv /usr/local/bin/dlv
EXPOSE 9080
# The distroless image has neither a shell nor an HTTP client, so the binary
# probes its own /health endpoint via the healthcheck command.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["/guldvegt", "healthcheck"]
USER nonroot:nonroot
ENTRYPOINT [ "/guldvegt" ]