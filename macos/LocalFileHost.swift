// LocalFileHost.app window.
//
// The page itself is the repository root index.html. The build script copies
// that file into Contents/Resources, so the browser page and this window
// cannot drift apart. This file is only the macOS window around that page.

import AppKit
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var indexURL: URL?

    // Capture-phase guard so a Finder drop cannot navigate the window away
    // from the app page. It does not stop propagation: index.html still
    // receives the drop and places the file.
    private static let fileDropGuard = """
    (function () {
      function hasFiles(event) {
        var types = event.dataTransfer && event.dataTransfer.types;
        if (!types) return false;
        for (var i = 0; i < types.length; i++) {
          if (types[i] === "Files") return true;
        }
        return false;
      }
      window.addEventListener("dragover", function (event) {
        if (!hasFiles(event)) return;
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
      }, true);
      window.addEventListener("drop", function (event) {
        if (!hasFiles(event)) return;
        event.preventDefault();
      }, true);
    })();
    """

    // Blocks network schemes inside the window. file:, blob:, and data: stay
    // available, so the bundled page and local media still load. This does not
    // affect opening the page from GitHub in a browser.
    private static let offlineContentRules = """
    [
      {"trigger":{"url-filter":"^https?://"},"action":{"type":"block"}},
      {"trigger":{"url-filter":"^wss?://"},"action":{"type":"block"}},
      {"trigger":{"url-filter":"^ftp://"},"action":{"type":"block"}}
    ]
    """

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        installMenus()

        guard
            let resourceURL = Bundle.main.resourceURL
        else {
            showMissingPageAndQuit()
            return
        }
        let pageURL = resourceURL.appendingPathComponent("index.html")
        guard FileManager.default.fileExists(atPath: pageURL.path) else {
            showMissingPageAndQuit()
            return
        }
        indexURL = pageURL

        let config = WKWebViewConfiguration()
        // Memory-only website data. The window does not keep a cookie jar or
        // HTTP cache on disk, and it does not record the files you open.
        config.websiteDataStore = WKWebsiteDataStore.nonPersistent()
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        let script = WKUserScript(
            source: AppDelegate.fileDropGuard,
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        )
        config.userContentController.addUserScript(script)

        WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "localfilehost-offline",
            encodedContentRuleList: AppDelegate.offlineContentRules
        ) { list, _ in
            DispatchQueue.main.async {
                if let list = list {
                    config.userContentController.add(list)
                }
                self.openWindow(config: config, pageURL: pageURL, resourceURL: resourceURL)
            }
        }
    }

    private func openWindow(config: WKWebViewConfiguration, pageURL: URL, resourceURL: URL) {
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = false
        webView.autoresizingMask = [.width, .height]
        self.webView = webView

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 920, height: 920),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Local Media Host"
        window.minSize = NSSize(width: 860, height: 780)
        window.isRestorable = false
        window.contentView = webView
        window.center()
        self.window = window

        webView.loadFileURL(pageURL, allowingReadAccessTo: resourceURL)
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(webView)
        if #available(macOS 14.0, *) {
            NSApp.activate()
        } else {
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        nil
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationResponse: WKNavigationResponse,
        decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void
    ) {
        let scheme = navigationResponse.response.url?.scheme?.lowercased()
        if scheme == "http" || scheme == "https" || scheme == "ws" || scheme == "wss" || scheme == "ftp" {
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
        true
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        let url = navigationAction.request.url
        let mainFrame = navigationAction.targetFrame?.isMainFrame ?? true
        if mainFrame {
            if isAppPage(url) || url?.scheme?.lowercased() == "about" {
                decisionHandler(.allow)
            } else {
                // Cancels a dropped file opening over the app. The page's
                // own drop handler still places the file.
                decisionHandler(.cancel)
            }
            return
        }
        // PDF embeds navigate the iframe to a blob: URL.
        let scheme = url?.scheme?.lowercased()
        if scheme == "blob" || scheme == "about" {
            decisionHandler(.allow)
        } else {
            decisionHandler(.cancel)
        }
    }

    private func isAppPage(_ url: URL?) -> Bool {
        guard let url, let indexURL, url.isFileURL else { return false }
        return url.standardizedFileURL.path == indexURL.standardizedFileURL.path
    }

    private func showMissingPageAndQuit() {
        let alert = NSAlert()
        alert.messageText = "LocalFileHost can't find its page"
        alert.informativeText = "Contents/Resources/index.html is missing from the app bundle."
        alert.runModal()
        NSApp.terminate(nil)
    }

    private func installMenus() {
        let main = NSMenu()

        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(NSMenuItem(
            title: "Quit LocalFileHost",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        ))

        let editItem = NSMenuItem()
        main.addItem(editItem)
        let edit = NSMenu(title: "Edit")
        editItem.submenu = edit
        edit.addItem(NSMenuItem(title: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x"))
        edit.addItem(NSMenuItem(title: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c"))
        edit.addItem(NSMenuItem(title: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v"))
        edit.addItem(NSMenuItem(title: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"))

        NSApp.mainMenu = main
    }
}

// swiftc entry point. No storyboard, so the delegate is installed here.
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
