ARG GOLANG_VERSION=1.27
ARG GOLANGCI_LINT_VERSION=2.13.0

# Lint stage
FROM golang:${GOLANG_VERSION} AS go-lint-stage
RUN go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.13.1
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

# Deploy the service into a separate lean image
FROM gcr.io/distroless/base-debian13 AS guldvegt-cmd
WORKDIR /
COPY --from=go-build-stage /guldvegt /guldvegt
#COPY --from=go-lint-stage /go/bin/dlv /usr/local/bin/dlv
EXPOSE 9080
USER nonroot:nonroot
ENTRYPOINT [ "/guldvegt" ]