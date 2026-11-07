"""Packaging checks that do not need a Mac or a browser.

A full LocalFileHost.app binary can only be compiled on macOS. These tests
check the shared page, the bundle layout, and that the build script refuses
to pretend it produced a binary anywhere else.
"""

import os
import plistlib
import platform
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
PLIST = ROOT / "macos" / "Info.plist"
SWIFT = ROOT / "macos" / "LocalFileHost.swift"
SCRIPT = ROOT / "scripts" / "build-macos-app.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "macos-app.yml"
APP = ROOT / "dist" / "LocalFileHost.app"


class PackagingTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(ROOT / "dist", ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(ROOT / "dist", ignore_errors=True)

    def test_page_keeps_browser_features_and_resize(self):
        text = INDEX.read_text(encoding="utf-8")
        for snippet in (
            'id="fileInput"',
            'accept="image/*,video/*,audio/*,application/pdf,text/*,.md,.json,.csv,.log"',
            "URL.createObjectURL",
            "function arrangeGrid()",
            "function clearScene()",
            "chooseFiles('video/*')",
            "chooseFiles('image/*')",
            "connect-src 'none'",
            "resize-handle",
            "function computeResize(",
            "Hold Shift to keep the aspect ratio",
            "closest('.resize-handle')",
            "stopPropagation",
            "anchorRight",
            "dataset.kind",
        ):
            self.assertIn(snippet, text)
        self.assertNotIn("<script src=", text)
        self.assertNotIn("<link rel=", text)
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)
        self.assertNotIn("sample-videos.com", text)
        self.assertNotIn("placehold.co", text)
        self.assertNotIn("localStorage", text)
        self.assertNotIn("indexedDB", text)
        self.assertNotIn("console.log", text)
        self.assertIn("isLocalResource", text)
        self.assertIn("navigator.sendBeacon", text)

    def test_plist_describes_an_unsigned_arm64_window_app(self):
        plist = plistlib.loads(PLIST.read_bytes())
        self.assertEqual(plist["CFBundleExecutable"], "LocalFileHost")
        self.assertEqual(plist["CFBundleName"], "LocalFileHost")
        self.assertEqual(plist["CFBundleDisplayName"], "LocalFileHost")
        self.assertEqual(plist["CFBundleIdentifier"], "io.github.techy702.localfilehost")
        self.assertEqual(plist["CFBundlePackageType"], "APPL")
        self.assertEqual(plist["LSMinimumSystemVersion"], "12.0")
        self.assertEqual(plist["NSPrincipalClass"], "NSApplication")
        self.assertTrue(plist["NSHighResolutionCapable"])
        self.assertNotIn("CFBundleIconFile", plist)
        self.assertNotIn("LSUIElement", plist)

    def test_wrapper_loads_the_shared_page(self):
        source = SWIFT.read_text(encoding="utf-8")
        self.assertIn("index.html", source)
        self.assertIn("loadFileURL", source)
        self.assertIn("WKWebView", source)
        self.assertIn("app.run()", source)
        self.assertIn("dropEffect", source)
        self.assertIn("WKWebsiteDataStore.nonPersistent()", source)
        self.assertIn("^https?://", source)
        self.assertIn("^wss?://", source)
        self.assertIn("isRestorable = false", source)
        self.assertNotIn("stopPropagation", source)
        self.assertNotIn("print(", source)
        self.assertNotIn("NSLog", source)
        self.assertNotIn("os_log", source)
        self.assertNotIn("MetricKit", source)
        self.assertNotIn("sample-videos.com", source)
        self.assertNotIn("placehold.co", source)
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("arm64-apple-macosx12.0", script)
        self.assertIn("codesign --force --sign -", script)
        self.assertIn('cp "$ROOT/index.html"', script)
        self.assertNotIn("APPLE_CERTIFICATE", script)
        self.assertNotIn("notarytool", script)
        self.assertNotIn("altool", script)
        self.assertNotIn("gh release", script)

    def test_workflow_builds_on_apple_silicon_and_does_not_publish(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: macos-15", workflow)
        self.assertIn("upload-artifact", workflow)
        self.assertIn("LocalFileHost-macos-arm64-unsigned", workflow)
        self.assertIn("tests.test_macos_packaging", workflow)
        self.assertIn("tests.test_resize_browser", workflow)
        self.assertNotIn("macos-14", workflow)
        for forbidden in (
            "create-release",
            "gh release",
            "softprops/action-gh-release",
            "secrets.",
        ):
            self.assertNotIn(forbidden, workflow)

    def test_build_script_syntax_and_help(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        help_run = subprocess.run(
            [str(SCRIPT), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("--stage-only", help_run.stdout)
        self.assertIn("Apple Silicon", help_run.stdout)
        unknown = subprocess.run(
            [str(SCRIPT), "--sign-for-real"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(unknown.returncode, 2)

    def test_stage_only_copies_the_same_page_and_no_binary(self):
        subprocess.run([str(SCRIPT), "--stage-only"], check=True, cwd=ROOT)
        bundled = APP / "Contents" / "Resources" / "index.html"
        self.assertEqual(bundled.read_bytes(), INDEX.read_bytes())
        plist = plistlib.loads((APP / "Contents" / "Info.plist").read_bytes())
        self.assertEqual(plist["CFBundleExecutable"], "LocalFileHost")
        self.assertTrue((APP / "Contents" / "MacOS").is_dir())
        self.assertFalse((APP / "Contents" / "MacOS" / "LocalFileHost").exists())
        self.assertFalse(any((APP / "Contents").rglob("*.icns")))

    def test_full_build_is_refused_off_macos(self):
        if platform.system() == "Darwin":
            self.skipTest("the macOS runner compiles the real binary")
        result = subprocess.run(
            [str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("macOS", result.stderr)
        self.assertFalse(APP.exists())


if __name__ == "__main__":
    unittest.main()
