# Tests › Runners › Rust › cargo-nextest
enforcer · A faster test runner for Rust.

- no recipe: Rust and cargo-nextest
- check: `cargo nextest run` in the crate

From the leaf's note:

Install: Rust (as in the cargo test note), then
`wget -qO- https://github.com/nextest-rs/nextest/releases/download/cargo-nextest-0.9.148/cargo-nextest-0.9.148-x86_64-unknown-linux-gnu.tar.gz | tar -xz -C /opt/enforce/cargo/bin`.
Use: `cd <crate> && RUSTUP_HOME=/opt/enforce/rustup /opt/enforce/cargo/bin/cargo nextest run`.

Docs: https://nexte.st/
