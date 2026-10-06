// Package api holds the HTTP contract generated from the repository's
// openapi.yaml: request/response types and the net/http ServerInterface.
//
// api.gen.go is generated — never edit it by hand. After changing openapi.yaml,
// run `go generate ./...` from the go/ directory and commit the result.
package api

//go:generate go run github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@v2.8.0 -config oapi-codegen.yaml ../../openapi.yaml
