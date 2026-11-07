#!/usr/bin/env bash
# Build LocalFileHost for the iOS Simulator and as an unsigned device bundle.
#
# Requires macOS with Xcode. Does not use a development team, certificate, or
# App Store Connect. The device .app is not installable on an iPhone or iPad
# until it is signed in Xcode with Matthew's team.
#
#   ./scripts/build-ios.sh
#
# Outputs:
#   dist/LocalFileHost-ios-simulator.zip
#   dist/LocalFileHost-ios-unsigned-device.zip
# Each zip contains LocalFileHost.app at the top level.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$ROOT/ios/LocalFileHost.xcodeproj"
SCHEME="LocalFileHost"
DIST="$ROOT/dist"
BUNDLE_ID="io.github.techy702.localfilehost.ios"

usage() {
  cat <<'EOF'
Usage: scripts/build-ios.sh

Build an iOS Simulator app and an unsigned iPhone/iPad app. Xcode is required.
No Apple ID, team, or signing secret is read. The unsigned device bundle
cannot be installed on a physical iPhone or iPad.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ $# -gt 0 ]]; then
  echo "Unknown option: $1" >&2
  usage >&2
  exit 2
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "iOS builds require macOS with Xcode." >&2
  echo "This machine cannot compile or launch the iOS Simulator." >&2
  exit 1
fi

if ! command -v xcodebuild >/dev/null 2>&1 || ! command -v xcrun >/dev/null 2>&1; then
  echo "Xcode is required (xcodebuild, xcrun)." >&2
  exit 1
fi

mkdir -p "$DIST"
SIM_DERIVED="$DIST/ios-simulator-derived"
DEVICE_DERIVED="$DIST/ios-device-derived"
rm -rf "$SIM_DERIVED" "$DEVICE_DERIVED"

xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination "generic/platform=iOS Simulator" \
  -derivedDataPath "$SIM_DERIVED" \
  CODE_SIGNING_ALLOWED=NO \
  build

xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination "generic/platform=iOS" \
  -derivedDataPath "$DEVICE_DERIVED" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY="" \
  build

SIM_APP="$(find "$SIM_DERIVED" -type d -name 'LocalFileHost.app' | head -n 1)"
DEVICE_APP="$(find "$DEVICE_DERIVED" -type d -name 'LocalFileHost.app' | head -n 1)"
if [[ -z "$SIM_APP" || -z "$DEVICE_APP" ]]; then
  echo "xcodebuild did not produce LocalFileHost.app" >&2
  exit 1
fi
if [[ ! -f "$SIM_APP/index.html" || ! -f "$DEVICE_APP/index.html" ]]; then
  echo "The iOS bundle is missing the shared index.html" >&2
  exit 1
fi

# Launch the simulator build, wait for the first paint, then screenshot while
# the app is still in front. This does not tap the screen or open the document picker.
python3 - "$SIM_APP" "$BUNDLE_ID" "$DIST/ios-simulator-launch.png" <<'PY'
import json, subprocess, sys, time
app, bundle, shot = sys.argv[1], sys.argv[2], sys.argv[3]
raw = subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"], text=True)
devices = json.loads(raw)["devices"]
chosen = None
for runtime, entries in devices.items():
    if "iOS" not in runtime:
        continue
    for entry in entries:
        if entry.get("isAvailable") and "iPhone" in entry.get("name", ""):
            chosen = entry
            break
    if chosen:
        break
if not chosen:
    sys.exit("No available iPhone simulator")
udid = chosen["udid"]
subprocess.run(["xcrun", "simctl", "boot", udid], check=False)
subprocess.run(["xcrun", "simctl", "bootstatus", udid, "-b"], check=True)
subprocess.run(["xcrun", "simctl", "install", udid, app], check=True)
# Return immediately so the app stays in the foreground. Closing a --console
# session sends the app away before the screenshot.
launched = subprocess.run(
    ["xcrun", "simctl", "launch", "--terminate-running-process", udid, bundle],
    check=True,
    capture_output=True,
    text=True,
)
print(launched.stdout.strip())
pid_text = launched.stdout.strip().rsplit(":", 1)[-1].strip()
time.sleep(4)
subprocess.run(["xcrun", "simctl", "io", udid, "screenshot", shot], check=True)
host_alive = False
if pid_text.isdigit():
    host_alive = subprocess.run(["kill", "-0", pid_text]).returncode == 0
listed = subprocess.run(
    ["xcrun", "simctl", "spawn", udid, "launchctl", "list"],
    capture_output=True,
    text=True,
)
sim_alive = bundle in (listed.stdout or "")
print(f"host_alive={host_alive} sim_launchctl={sim_alive}")
if not host_alive and not sim_alive:
    sys.exit("LocalFileHost was not running when the screenshot was taken")
print(f"Simulator {chosen['name']} kept LocalFileHost running")
PY

zip_app() {
  local app_path="$1"
  local zip_path="$2"
  rm -f "$zip_path"
  ditto -c -k --keepParent "$app_path" "$zip_path"
  python3 - "$zip_path" <<'PY'
import sys, zipfile
path = sys.argv[1]
names = [name.replace("\\", "/") for name in zipfile.ZipFile(path).namelist()]
if any(name == "Contents" or name.startswith("Contents/") for name in names):
    sys.exit("zip root is a bare Contents directory")
if not any(name.startswith("LocalFileHost.app/") for name in names):
    sys.exit("LocalFileHost.app is not the top-level bundle")
print("LocalFileHost.app is the top-level bundle in", path)
PY
}

zip_app "$SIM_APP" "$DIST/LocalFileHost-ios-simulator.zip"
zip_app "$DEVICE_APP" "$DIST/LocalFileHost-ios-unsigned-device.zip"
echo "Simulator zip: $DIST/LocalFileHost-ios-simulator.zip"
echo "Unsigned device zip: $DIST/LocalFileHost-ios-unsigned-device.zip"
echo "The device zip is not installable on an iPhone or iPad without signing."
