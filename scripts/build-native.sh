#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../native"
if ! command -v cargo >/dev/null; then
  echo 'Install Rust 1.85+ and run: rustup target add armv7-unknown-linux-musleabihf' >&2
  exit 1
fi
cargo build --locked --release --target armv7-unknown-linux-musleabihf --features arm-asm
