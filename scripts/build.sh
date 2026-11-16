#!/usr/bin/env bash
# Build a distributable IPK with local, locked tooling and no personal API keys.
set -euo pipefail
cd "$(dirname "$0")/.."
node scripts/check_es5.js
if [ "${1:-}" != "--web-only" ]; then
  bash scripts/build-native.sh
fi
package_tool="${PWD}/node_modules/.bin/ares-package"
if [ ! -x "$package_tool" ]; then
  echo "Missing webOS CLI. Run npm ci first." >&2
  exit 1
fi
stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT
mkdir -p "$stage_dir/app"
cp app/index.html app/style.css app/app.js app/native.js app/appinfo.json app/icon.png app/largeIcon.png "$stage_dir/app/"
cp app/config.example.js "$stage_dir/app/config.js"
cp LICENSE "$stage_dir/app/LICENSE"
mkdir -p dist
if [ "${1:-}" = "--web-only" ]; then
  mkdir -p dist/web-only
  "$package_tool" "$stage_dir/app" -o dist/web-only
else
  mkdir -p "$stage_dir/service"
  cp service/package.json service/services.json service/service.js service/runner.js "$stage_dir/service/"
  cp native/target/armv7-unknown-linux-musleabihf/release/streamlite-core "$stage_dir/service/"
  chmod 755 "$stage_dir/service/streamlite-core"
  python scripts/native_licenses.py "$stage_dir/service/licenses"
  "$package_tool" "$stage_dir/app" "$stage_dir/service" -o dist
fi
ls -1 dist/*.ipk
