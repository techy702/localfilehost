# Local Media Host

A single-page, browser-based tool for arranging media elements on a canvas, in the spirit of OBS.

[Launch LocalFileHost](https://techy702.github.io/localfilehost/)

## Features

- Drag and drop images, video, audio, PDFs and text files (`.txt`, `.md`, `.json`, `.csv`, `.log`) from your file manager (Finder, Explorer) onto the drop zone or the canvas, or click the drop zone to choose files
- Files dropped on the canvas land where you drop them
- Images and video are sized to their natural dimensions, scaled down to fit the canvas if larger
- Add a sample video, a placeholder image, or a text box with the toolbar buttons
- Reposition elements on the canvas by dragging them
- Drag the blue corner handles to resize an item. The opposite corner stays where it is, so the resize does not pick the item up and move it
- Hold Shift while resizing to keep the item's aspect ratio. Without Shift, width and height change independently. Images and video use `object-fit: contain`, so the media stays fully visible inside the new box
- While shrinking, items stop at a minimum size: images 48×48, video 160×90, text 80×48, audio 180×40, PDFs 120×120. An item that is already smaller than that cannot be shrunk further. A resize also stops at the canvas edge
- Video and audio playback through the browser's built-in controls
- Auto Arrange tiles everything into a grid (automatic or 1-4 columns), scaling each item to fit its cell
- Clear the whole canvas with one click

## Usage

1. Open `index.html` in your browser, or launch the macOS app described below.
2. Drag files onto the canvas or the dashed drop zone above it, click the drop zone to choose files, or use the **Add Video**, **Add Image** and **Add Text** buttons.
3. Click and drag an element on the canvas to reposition it.
4. Drag a corner handle to resize it. Drag the south-east handle to change width and height together from the top-left corner. The other corners keep the opposite edges in place. Hold Shift to lock the aspect ratio.
5. Click **Auto Arrange** to tile everything into a grid. Pick the number of columns first, or leave it on Auto.
6. Use **Clear Scene** to remove everything.

## Requirements

- A modern web browser (Chrome, Firefox, Safari), or the macOS app below
- Internet access only for the sample video and placeholder image added by the **Add Video** and **Add Image** buttons. Files you drop in are read locally. Opening the page, picking local files, and playback of those files work offline

## macOS app

`LocalFileHost.app` is a Finder-visible Apple Silicon application. It opens one window and loads the same `index.html` that GitHub Pages serves. The build copies that file into the app; there is no second copy of the page. Corner resize, file picking, drag and drop, playback, text, and Auto Arrange are the page's behavior in both places.

The window is a small AppKit + WKWebView wrapper (`macos/LocalFileHost.swift`). Dropped files stay in the page: a short script cancels the web view navigating away to a file, and the page's own drop handler still places the file. There is no custom icon. Finder shows the generic application icon.

This packaging was prepared without a Mac. The binary was not compiled here and the window was not launched here. A Mac is still required to produce and run `LocalFileHost.app`.

### Build

On an Apple Silicon Mac, install the Xcode Command Line Tools if you do not already have them:

```bash
xcode-select --install
./scripts/build-macos-app.sh
```

The script compiles `macos/LocalFileHost.swift` for `arm64-apple-macosx12.0` (macOS 12 or later, Apple Silicon only), copies `index.html` into the bundle, and ad-hoc signs it with `codesign --sign -`. It does not read an Apple Developer certificate, password, or notarization secret.

Output: `dist/LocalFileHost.app`

To check the bundle layout on a machine that is not a Mac:

```bash
./scripts/build-macos-app.sh --stage-only
```

That writes `Info.plist` and `index.html` only. It does not create a binary, and that folder is not a runnable app.

### Install and run

```bash
cp -R dist/LocalFileHost.app /Applications/
open /Applications/LocalFileHost.app
```

You can also double-click `dist/LocalFileHost.app` in Finder. The app quits when its window is closed. Local files work offline. **Add Video** and **Add Image** still load their sample URLs from the network.

### GitHub Actions

`.github/workflows/macos-app.yml` is the reproducible build. It runs on pull requests and when started by hand (`workflow_dispatch`):

- Ubuntu runs the packaging tests and the browser resize tests
- `macos-15` (Apple Silicon) runs `./scripts/build-macos-app.sh` and uploads the artifact `LocalFileHost-macos-arm64-unsigned`

The workflow does not create a GitHub Release. `macos-14` runners were retired on 2 November 2026, so the Apple Silicon label is `macos-15`.

### Unsigned app limitations

The ad-hoc signature lets Apple Silicon macOS launch a local binary. It is not a Developer ID or App Store signature, and the app is not notarized.

- Gatekeeper rejects a downloaded copy, including a copy saved from the Actions artifact. macOS may say the app is from an unidentified developer, or that it is damaged and cannot be opened. The file is not damaged; quarantine plus a missing notarization ticket causes that message
- For an app you built on that Mac and did not download, double-click `dist/LocalFileHost.app`. It usually opens without the download warning
- For a downloaded copy: Control-click the app in Finder, choose **Open**, then **Open** again. If macOS still reports it as damaged, clear the download flag and open it again: `xattr -dr com.apple.quarantine /path/to/LocalFileHost.app`. That removes the quarantine flag for this app only. It does not notarize the app
- `spctl --assess` still fails. That is expected
- Apple Silicon only. The binary is arm64 and does not run on Intel Macs
- The app is not sandboxed and has no special entitlements. It reads files the same way the browser page does: through the file picker and drag and drop
- No custom icon is included

### What still needs a Mac

Compiling the Swift window, ad-hoc signing, confirming the Mach-O is arm64, and actually opening the window (Finder drag and drop, Gatekeeper, playback inside WKWebView) all happen on a Mac. The browser tests below cover the shared page, which is what the window loads. They do not launch the `.app`.

## Development

The browser app is one `index.html` file. It has no build step and no dependencies. GitHub Pages serves that file from the repository root.

The macOS app is an optional wrapper around the same file. `dist/` is gitignored.

### Tests

Packaging checks (no Mac and no browser):

```bash
python3 -m unittest tests.test_macos_packaging
```

Page interactions in Chromium (resize handles, dragging, the file picker, image/video/audio/text/PDF, Auto Arrange). Requires Python, Playwright, and ffmpeg. The test uses installed Google Chrome when `channel="chrome"` works, and otherwise Playwright's Chromium:

```bash
pip install -r tests/requirements.txt
python3 -m unittest tests.test_resize_browser
```

## Contributing

Feel free to fork and submit pull requests.

## License

MIT License. See [LICENSE](LICENSE) for details.
