# Local Media Host

A single-page, browser-based tool for arranging media elements on a canvas, in the spirit of OBS.

## Features

- Drag and drop image and video files from your file manager (Finder, Explorer) onto the drop zone or the canvas, or click the drop zone to choose files
- Add a sample video, a placeholder image, or a text box with the toolbar buttons
- Reposition elements on the canvas by dragging them
- Video playback through the browser's built-in controls
- Clear the whole canvas with one click

## Usage

1. Open `index.html` in your browser.
2. Drag image or video files onto the canvas or the dashed drop zone above it, click the drop zone to choose files, or use the **Add Video**, **Add Image** and **Add Text** buttons.
3. Click and drag an element on the canvas to reposition it.
4. Use **Clear Scene** to remove everything.

## Requirements

- A modern web browser (Chrome, Firefox, Safari)
- Internet access only for the sample video and placeholder image added by the **Add Video** and **Add Image** buttons. Files you drop in are read locally.

## Development

The whole app is one `index.html` using HTML5, CSS and JavaScript. There is no build step and there are no dependencies.

## Contributing

Feel free to fork and submit pull requests.

## License

MIT License. See [LICENSE](LICENSE) for details.
