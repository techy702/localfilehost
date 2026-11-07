#!/usr/bin/env python3
"""Check that a macOS artifact zip keeps LocalFileHost.app as its top level.

GitHub's artifact download wraps this zip in a second zip. After both
extractions, Finder must show LocalFileHost.app, not a bare Contents folder.
"""

import sys
import zipfile


def problems(names):
    names = [name.replace("\\", "/") for name in names]
    found = []
    if any(name == "Contents" or name.startswith("Contents/") for name in names):
        found.append("archive root is a bare Contents directory")
    if not any(name.startswith("LocalFileHost.app/") for name in names):
        found.append("LocalFileHost.app is not the top-level bundle")
    plist = "LocalFileHost.app/Contents/Info.plist"
    binary = "LocalFileHost.app/Contents/MacOS/LocalFileHost"
    if plist not in names:
        found.append("missing " + plist)
    if binary not in names:
        found.append("missing " + binary)
    return found


def main():
    if len(sys.argv) != 2:
        print("usage: verify-macos-artifact-zip.py <artifact.zip>", file=sys.stderr)
        return 2
    with zipfile.ZipFile(sys.argv[1]) as archive:
        found = problems(archive.namelist())
    if found:
        print("\n".join(found), file=sys.stderr)
        return 1
    print("LocalFileHost.app is the top-level bundle in", sys.argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
