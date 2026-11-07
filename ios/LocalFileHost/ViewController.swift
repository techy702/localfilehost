import UIKit
import UniformTypeIdentifiers
import WebKit

// Loads the same index.html as the browser and the Mac app. Media stays in the
// page. This controller does not log filenames or send analytics.
final class ViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, UIDocumentPickerDelegate {
    private var webView: WKWebView!
    private var indexURL: URL?
    private var presentingCanvas = false
    private var openPanelCompletion: (([URL]?) -> Void)?

    private static let offlineContentRules = """
    [
      {"trigger":{"url-filter":"^https?://"},"action":{"type":"block"}},
      {"trigger":{"url-filter":"^wss?://"},"action":{"type":"block"}},
      {"trigger":{"url-filter":"^ftp://"},"action":{"type":"block"}}
    ]
    """

    override var prefersStatusBarHidden: Bool { presentingCanvas }
    override var prefersHomeIndicatorAutoHidden: Bool { presentingCanvas }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        guard
            let pageURL = Bundle.main.url(forResource: "index", withExtension: "html")
        else {
            showMissingPage()
            return
        }
        indexURL = pageURL

        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        let controller = config.userContentController
        controller.add(self, name: "localFileHost")

        let webView = WKWebView(frame: view.bounds, configuration: config)
        webView.allowsBackForwardNavigationGestures = false
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.bounces = false
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
        ])
        self.webView = webView

        WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "localfilehost-offline-ios",
            encodedContentRuleList: Self.offlineContentRules
        ) { [weak self] list, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if let list = list {
                    self.webView.configuration.userContentController.add(list)
                }
                self.webView.loadFileURL(pageURL, allowingReadAccessTo: pageURL.deletingLastPathComponent())
            }
        }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "localFileHost", let action = message.body as? String else { return }
        if action == "enterFullscreen" {
            presentingCanvas = true
        } else if action == "exitFullscreen" {
            presentingCanvas = false
        } else {
            return
        }
        setNeedsStatusBarAppearanceUpdate()
        setNeedsUpdateOfHomeIndicatorAutoHidden()
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
                decisionHandler(.cancel)
            }
            return
        }
        let scheme = url?.scheme?.lowercased()
        if scheme == "blob" || scheme == "about" {
            decisionHandler(.allow)
        } else {
            decisionHandler(.cancel)
        }
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

    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        nil
    }

    // iOS 18.4 and later ask the app to show the document picker for <input type="file">.
    // Older systems present it themselves. Cancel passes nil and does not record a path.
    @available(iOS 18.4, *)
    func webView(
        _ webView: WKWebView,
        runOpenPanelWith parameters: WKOpenPanelParameters,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping ([URL]?) -> Void
    ) {
        if openPanelCompletion != nil {
            completionHandler(nil)
            return
        }
        openPanelCompletion = completionHandler
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: Self.mediaContentTypes, asCopy: false)
        picker.allowsMultipleSelection = parameters.allowsMultipleSelection
        picker.delegate = self
        present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        for url in urls {
            _ = url.startAccessingSecurityScopedResource()
        }
        openPanelCompletion?(urls)
        openPanelCompletion = nil
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        openPanelCompletion?(nil)
        openPanelCompletion = nil
    }

    private static var mediaContentTypes: [UTType] {
        var types: [UTType] = [.image, .movie, .audio, .pdf, .plainText, .text, .json]
        if let csv = UTType(filenameExtension: "csv") { types.append(csv) }
        if let markdown = UTType(filenameExtension: "md") { types.append(markdown) }
        if let log = UTType(filenameExtension: "log") { types.append(log) }
        return types
    }

    private func isAppPage(_ url: URL?) -> Bool {
        guard let url, let indexURL, url.isFileURL else { return false }
        return url.standardizedFileURL.path == indexURL.standardizedFileURL.path
    }

    private func showMissingPage() {
        let label = UILabel()
        label.text = "LocalFileHost can't find its page"
        label.textAlignment = .center
        label.numberOfLines = 0
        label.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: view.layoutMarginsGuide.leadingAnchor),
            label.trailingAnchor.constraint(equalTo: view.layoutMarginsGuide.trailingAnchor),
            label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
        ])
    }
}
