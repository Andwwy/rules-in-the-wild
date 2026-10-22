# Tests › Runners › go test
enforcer · Go's own test runner.

- no recipe: Go
- check: `go test ./...` in the module

From the leaf's note:

Install: `wget -qO- https://go.dev/dl/go1.27.2.linux-amd64.tar.gz | tar -xz -C /opt/enforce` (`/opt/enforce/go/bin/go`).
Use: `cd <module> && /opt/enforce/go/bin/go test -json ./...`.

Docs: https://pkg.go.dev/cmd/go#hdr-Test_packages
