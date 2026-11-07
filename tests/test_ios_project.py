"""Checks for the iOS project that do not need a Mac or a simulator."""

import os
import plistlib
import platform
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
PLIST = ROOT / "ios" / "LocalFileHost" / "Info.plist"
PROJECT = ROOT / "ios" / "LocalFileHost.xcodeproj" / "project.pbxproj"
SCHEME = ROOT / "ios" / "LocalFileHost.xcodeproj" / "xcshareddata" / "xcschemes" / "LocalFileHost.xcscheme"
SCRIPT = ROOT / "scripts" / "build-ios.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "macos-app.yml"
CONTROLLER = ROOT / "ios" / "LocalFileHost" / "ViewController.swift"


class IOSProjectTests(unittest.TestCase):
    def test_project_files_exist(self):
        for path in (PLIST, PROJECT, SCHEME, SCRIPT, CONTROLLER):
            self.assertTrue(path.is_file(), path)
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_plist_has_no_extra_permissions(self):
        plist = plistlib.loads(PLIST.read_bytes())
        self.assertEqual(plist["CFBundleDisplayName"], "LocalFileHost")
        self.assertTrue(plist["LSRequiresIPhoneOS"])
        orientations = plist["UISupportedInterfaceOrientations"]
        self.assertIn("UIInterfaceOrientationPortrait", orientations)
        self.assertIn("UIInterfaceOrientationLandscapeLeft", orientations)
        ipad = plist["UISupportedInterfaceOrientations~ipad"]
        self.assertGreaterEqual(len(ipad), 4)
        text = PLIST.read_text(encoding="utf-8")
        for forbidden in (
            "NSCameraUsageDescription",
            "NSPhotoLibraryUsageDescription",
            "NSMicrophoneUsageDescription",
            "NSLocationWhenInUseUsageDescription",
            "NSAllowsArbitraryLoads",
        ):
            self.assertNotIn(forbidden, text)

    def test_target_is_iphone_and_ipad_without_a_team(self):
        project = PROJECT.read_text(encoding="utf-8")
        self.assertIn("io.github.techy702.localfilehost.ios", project)
        self.assertIn('TARGETED_DEVICE_FAMILY = "1,2"', project)
        self.assertIn("IPHONEOS_DEPLOYMENT_TARGET = 16.0", project)
        self.assertIn("CODE_SIGNING_ALLOWED = NO", project)
        self.assertIn('DEVELOPMENT_TEAM = ""', project)
        self.assertIn("index.html", project)
        self.assertIn("LocalFileHost", SCHEME.read_text(encoding="utf-8"))

    def test_controller_blocks_network_and_presents_documents(self):
        source = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn(".nonPersistent()", source)
        self.assertIn("runOpenPanelWith", source)
        self.assertIn("documentPickerWasCancelled", source)
        self.assertIn("completionHandler(nil)", source)
        self.assertIn("^https?://", source)
        self.assertIn("loadFileURL", source)
        self.assertIn("allowsBackForwardNavigationGestures = false", source)
        self.assertNotIn("print(", source)
        self.assertNotIn("NSLog", source)
        self.assertNotIn("os_log", source)
        page = INDEX.read_text(encoding="utf-8")
        self.assertIn("safe-area-inset-top", page)
        self.assertIn("viewport-fit=cover", page)
        self.assertIn("touch-action: none", page)
        self.assertIn("overscroll-behavior: none", page)
        self.assertIn("messageHandlers", page)

    def test_workflow_builds_ios_without_a_release(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("./scripts/build-ios.sh", workflow)
        self.assertIn("LocalFileHost-ios-simulator", workflow)
        self.assertIn("LocalFileHost-ios-unsigned-device", workflow)
        self.assertNotIn("testflight", workflow.lower())
        self.assertNotIn("app-store", workflow.lower())

    def test_full_build_is_refused_off_macos(self):
        if platform.system() == "Darwin":
            self.skipTest("the macOS runner compiles the iOS bundles")
        result = subprocess.run([str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("macOS", result.stderr)


if __name__ == "__main__":
    unittest.main()
