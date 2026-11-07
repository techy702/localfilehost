# Local Media Host

A single-page, browser-based tool for arranging media elements on a canvas, in the spirit of OBS.

[Launch LocalFileHost](https://techy702.github.io/localfilehost/)

## Features

- Drag and drop images, video, audio, PDFs and text files (`.txt`, `.md`, `.json`, `.csv`, `.log`) from your file manager (Finder, Explorer) onto the drop zone or the canvas, or click the drop zone to choose files
- Files dropped on the canvas land where you drop them
- Images and video are sized to their natural dimensions, scaled down to fit the canvas if larger
- **Add Video** and **Add Image** open the file picker for a local file. **Add Text** places a text box. None of these contact a server
- Drag an item partly or fully off the canvas, and resize it larger than the canvas, so a widescreen picture can line up with a frame that sits on top. The canvas clips drawing. The Layers list still selects an item that is outside, and **Bring into view** pulls a grabbable edge back on screen
- Layers: **Front**, **Forward**, **Backward**, and **Back** change which item is painted above another, so a video can sit behind a border image
- The opacity slider changes the selected item
- **Mute All** and **Loop All** apply to every video and audio element, including ones added afterward. The button label shows On or Off. **Clear Scene** does not turn them off
- Dragging a video and releasing the mouse leaves playback running. A later click on the video's own controls still pauses or plays it
- **Sources** lists the topmost item first. Drag a row, or use **Up** and **Down**, to restack it. **Hide** keeps the row selectable. **Lock** stops accidental moves and resizes until **Unlock**. The name field is only kept in this window
- **Fullscreen** hides the editor and scales the whole canvas to the screen without stretching it. Video and images stay the original files. Making the canvas larger does not add detail the file does not have. **Exit fullscreen** or Escape returns to the editor and leaves playback as it was
- Click a selected text source, or double-click it, and edit the words in the **Text** box under Sources. Line breaks are kept. The text is shown as typed, including any characters that look like HTML. The name is not saved and is not sent anywhere
- Corner handles appear on the selected item while you adjust it, then hide when you release. Click the item again, or move the pointer back onto it, to resize again. Click empty canvas or press Escape to deselect. Locked items, hidden items, and fullscreen do not show handles
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
7. Click **Fullscreen** to present the canvas. Use **Exit fullscreen** or Escape to come back.

## Requirements

- A modern web browser (Chrome, Firefox, Safari), or the macOS app below
- The page itself can be downloaded from GitHub Pages. That download is only the app page. Choosing a file, playing it, and resizing it do not send the file name, the file, or playback activity anywhere
- A saved `index.html` and the Mac app open local files with no network connection

## Privacy

LocalFileHost does not upload files you open, and it does not report filenames, file details, or playback to a server.

- The [GitHub Pages](https://techy702.github.io/localfilehost/) link downloads this page from GitHub. GitHub can see that request for the page. It is made before you pick a file. It does not include which file you open later, and it does not report play, pause, or seeking.
- After the page is open, its code does not call out. **Add Video** and **Add Image** open the local file picker. Dropped and chosen files are read into memory and shown with `blob:` URLs. Text files are read into the page the same way. A `blob:` URL is local even when the page address itself came from GitHub.
- The Mac app loads the copy of `index.html` stored inside the app. Starting the app does not download the page from GitHub, and its window blocks `http`, `https`, `ws`, `wss`, and `ftp` loads.
- The canvas is not saved. **Clear Scene** drops it. Closing the tab or quitting the app drops it. The app does not write a filename log, analytics, or its own crash report.
- The Mac window uses a memory-only WebKit data store and does not restore the window contents. It does not keep a cookie jar or HTTP cache on disk for this app.

This does not control the rest of the computer:

- Anyone who can see the screen can see what is playing. Other apps, browser extensions, and the operating system are outside this app.
- A browser that opened the GitHub Pages copy may keep a history entry for that page address. That entry is the page URL, not the local file you played.
- If the app or the browser crashes, macOS or the browser may write a crash report under that system's own settings. This app does not create or send those reports. A system crash report can include process memory, so a crash dump is not guaranteed to be free of media data.
- The system file dialog is how a file is chosen. This app does not transmit that choice.
- A PDF is shown from a local `blob:` in a frame that is not allowed to navigate to the web. These tests did not execute every PDF engine on a Mac.

There is no absolute guarantee. The controls are the page policy and, in the Mac app, the WebKit rules shipped with it.

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

You can also double-click `dist/LocalFileHost.app` in Finder. The app quits when its window is closed. Local files play with no network connection. **Add Video** and **Add Image** open the file picker.

### GitHub Actions

`.github/workflows/macos-app.yml` is the reproducible build. It runs on pull requests and when started by hand (`workflow_dispatch`):

- Ubuntu runs the packaging tests and the browser resize tests
- `macos-15` (Apple Silicon) runs `./scripts/build-macos-app.sh` and uploads the artifact `LocalFileHost-macos-arm64-unsigned`

The uploaded file is `LocalFileHost-macos-arm64-unsigned.zip`. GitHub wraps that file in a second zip when you download the artifact. The inner zip's top folder is `LocalFileHost.app`, not a bare `Contents` directory. The build checks that layout before upload.

Extract it this way:

1. Unzip GitHub's download. You get `LocalFileHost-macos-arm64-unsigned.zip`.
2. Unzip that inner archive. On a Mac, double-click it or run `ditto -x -k LocalFileHost-macos-arm64-unsigned.zip .`
3. Open `LocalFileHost.app`.

An older artifact unpacked straight to `Contents` (with `MacOS`, `Resources`, and `Info.plist`) in Downloads. That folder is not the app. Use a build from this packaging fix.

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

Compiling the Swift window, ad-hoc signing, confirming the Mach-O is arm64, and actually opening the window still happen on a Mac. That includes Finder drag and drop, Gatekeeper, playback inside WKWebView, and whether the WebKit content rule blocks a live network attempt in the app process. The browser tests below cover the shared page, which is what the window loads, including an observation that a deliberate outbound request is not issued. They do not launch the `.app`. An Actions artifact built before this privacy change does not include it.

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
