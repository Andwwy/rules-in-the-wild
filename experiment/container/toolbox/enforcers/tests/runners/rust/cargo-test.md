# Tests › Runners › Rust › cargo test
enforcer · Rust's own test runner.

- no recipe: Rust
- check: `cargo test --quiet` in the crate

From the leaf's note:

Install: `apt-get update && apt-get install -y gcc`, then
`wget -q https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init -O /tmp/rustup-init && chmod +x /tmp/rustup-init && RUSTUP_HOME=/opt/enforce/rustup CARGO_HOME=/opt/enforce/cargo /tmp/rustup-init -y --profile minimal --default-toolchain 1.99.1 --no-modify-path`.
Use: `cd <crate> && RUSTUP_HOME=/opt/enforce/rustup /opt/enforce/cargo/bin/cargo test`.

Docs: https://doc.rust-lang.org/cargo/commands/cargo-test.html
