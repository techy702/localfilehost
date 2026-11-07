#!/usr/bin/env bash
# Build an unsigned Apple Silicon LocalFileHost.app.
#
# The app window loads the repository's index.html. This script copies that
# file into the bundle; it does not keep a second copy of the page.
#
# A runnable build requires an Apple Silicon Mac (or an Apple Silicon macOS
# CI runner) with Xcode Command Line Tools. No Apple Developer account,
# certificate, notarization secret, or provisioning profile is used.
# The binary is ad-hoc signed (`codesign --sign -`) so macOS will launch it.
# That is not a Developer ID signature. See the README for Gatekeeper limits.
#
#   ./scripts/build-macos-app.sh
#   ./scripts/build-macos-app.sh --stage-only
#
# --stage-only assembles Contents/Info.plist and Contents/Resources/index.html
# and then stops. It does not compile and the result is not a runnable app.
# Use it to check the bundle layout on Linux or any other OS.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="LocalFileHost"
APP="$ROOT/dist/${APP_NAME}.app"
DEPLOYMENT_TARGET="12.0"
STAGE_ONLY=0

usage() {
  cat <<'EOF'
Usage: scripts/build-macos-app.sh [--stage-only]

Assemble dist/LocalFileHost.app from macos/Info.plist, macos/LocalFileHost.swift,
and the repository root index.html.

  --stage-only   Copy the bundle layout and index.html, then stop before
                 compiling. The result is not a runnable app.

A full build must run on an Apple Silicon Mac with Xcode Command Line Tools
(swiftc, codesign, xcrun). It compiles for arm64-apple-macosx12.0 and
ad-hoc signs the bundle. No Apple Developer account or signing secret is read.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage-only) STAGE_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$STAGE_ONLY" -eq 0 && "$(uname -s)" != "Darwin" ]]; then
  echo "A runnable LocalFileHost.app can only be compiled on macOS." >&2
  echo "Re-run this script on an Apple Silicon Mac, or pass --stage-only to assemble resources without a binary." >&2
  exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$ROOT/macos/Info.plist" "$APP/Contents/Info.plist"
cp "$ROOT/index.html" "$APP/Contents/Resources/index.html"

if [[ "$STAGE_ONLY" -eq 1 ]]; then
  echo "Staged $APP"
  echo "Not runnable: no Mac binary was compiled."
  exit 0
fi

if ! command -v swiftc >/dev/null 2>&1 || ! command -v codesign >/dev/null 2>&1 || ! command -v xcrun >/dev/null 2>&1; then
  echo "Xcode Command Line Tools are required (swiftc, codesign, xcrun)." >&2
  echo "Install them with: xcode-select --install" >&2
  exit 1
fi

SDK="$(xcrun --sdk macosx --show-sdk-path)"
swiftc \
  -target "arm64-apple-macosx${DEPLOYMENT_TARGET}" \
  -sdk "$SDK" \
  -framework AppKit \
  -framework WebKit \
  -O \
  -o "$APP/Contents/MacOS/$APP_NAME" \
  "$ROOT/macos/LocalFileHost.swift"
chmod 755 "$APP/Contents/MacOS/$APP_NAME"

# Ad-hoc signature only. This does not contact Apple and does not use a certificate.
codesign --force --sign - "$APP/Contents/MacOS/$APP_NAME"
codesign --force --sign - "$APP"
codesign --verify --strict --verbose=2 "$APP"

ARCHS="$(lipo -archs "$APP/Contents/MacOS/$APP_NAME")"
case " $ARCHS " in
  *" x86_64 "*)
    echo "Expected an Apple Silicon (arm64) binary only, got: $ARCHS" >&2
    exit 1
    ;;
  *" arm64 "*) ;;
  *)
    echo "Expected an arm64 binary, got: $ARCHS" >&2
    exit 1
    ;;
esac

cmp -s "$ROOT/index.html" "$APP/Contents/Resources/index.html"

if command -v plutil >/dev/null 2>&1; then
  plutil -lint "$APP/Contents/Info.plist"
fi

echo "Built $APP"
echo "Apple Silicon only (arch: $ARCHS). Ad-hoc signed, not notarized."
echo "Gatekeeper will still block copies that were downloaded. See the README."

# Keep LocalFileHost.app as the top-level folder inside the zip. Uploading the
# .app directory itself makes GitHub's artifact extract to a bare Contents folder.
ZIP="$ROOT/dist/LocalFileHost-macos-arm64-unsigned.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
python3 "$ROOT/scripts/verify-macos-artifact-zip.py" "$ZIP"
echo "Artifact zip: $ZIP"
