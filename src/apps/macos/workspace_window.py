"""A reusable native window for the local workspace; Cocoa calls run on the main thread."""

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from src.apps.macos.workspace_server import same_origin, workspace_url

BRIDGE_SCRIPT = r"""
(() => {
  let sequence = 0;
  const waiting = new Map();
  addEventListener('rma-native-response', event => {
    const response = event.detail;
    const item = waiting.get(response.id);
    if (!item) return;
    clearTimeout(item.timer); waiting.delete(response.id);
    response.success ? item.resolve(response.data) : item.reject(new Error(response.error || 'Native action failed'));
  });
  const send = (action, text) => new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => {waiting.delete(id); reject(new Error('Native action timed out'));}, 60000);
    waiting.set(id, {resolve, reject, timer});
    window.webkit.messageHandlers.roastmyaudio.postMessage({id, action, text});
  });
  window.roastmyaudioDesktop = Object.freeze({
    copy: text => send('copy', text),
    exportText: text => send('export', text),
    command: (action, payload = {}) => send('command', JSON.stringify({action, payload})),
    saveDraft: draft => send('draft', draft),
  });
})();
"""


def validate_bridge_message(body, source_url, base_url, main_frame):
    """The clipboard/save bridge accepts bounded text from our main frame only."""
    if not main_frame or not same_origin(source_url, base_url):
        raise ValueError("Native actions require the local workspace main frame")
    if not isinstance(body, dict) or body.get("action") not in {
        "copy",
        "export",
        "phase",
        "command",
        "draft",
    }:
        raise ValueError("Unsupported native action")
    if type(body.get("id")) is not int or not isinstance(body.get("text"), str):
        raise ValueError("Invalid native action payload")
    if body["action"] == "phase" and body["text"] not in {
        "idle",
        "requesting",
        "recording",
        "processing",
    }:
        raise ValueError("Invalid recording phase")
    if len(body["text"]) > 2_000_000:
        raise ValueError("Text is too large for this action")
    return body


@lru_cache(maxsize=1)
def _native_types():
    import AppKit
    import Foundation
    import objc
    import WebKit
    from AppKit import (
        NSModalResponseOK,
        NSPasteboard,
        NSSavePanel,
        NSStringPboardType,
        NSWorkspace,
    )
    from Foundation import NSURL, NSJSONSerialization, NSObject
    from WebKit import (
        WKNavigationActionPolicyAllow,
        WKNavigationActionPolicyCancel,
        WKNavigationTypeLinkActivated,
        WKPermissionDecisionDeny,
    )

    class RMAWorkspaceDelegate(NSObject):
        @objc.python_method
        def configure(self, owner):
            self.owner = owner

        def windowShouldClose_(self, window):
            self.owner.webview.evaluateJavaScript_completionHandler_(
                "window.dispatchEvent(new Event('rma-workspace-closing'));", None
            )
            return True

        def webView_decidePolicyForNavigationAction_decisionHandler_(
            self, webview, action, decision
        ):
            url = str(action.request().URL().absoluteString())
            if same_origin(url, self.owner.base_url):
                decision(WKNavigationActionPolicyAllow)
            else:
                decision(WKNavigationActionPolicyCancel)
                if (
                    action.navigationType() == WKNavigationTypeLinkActivated
                    and urlsplit(url).scheme == "https"
                ):
                    NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

        def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
            self, webview, config, action, features
        ):
            url = str(action.request().URL().absoluteString())
            if (
                action.navigationType() == WKNavigationTypeLinkActivated
                and urlsplit(url).scheme == "https"
            ):
                NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))
            return None

        def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
            self, webview, origin, frame, capture_type, decision
        ):
            # The desktop always uses its native controller; WebKit never captures media.
            decision(WKPermissionDecisionDeny)

        def userContentController_didReceiveScriptMessage_(self, controller, message):
            identifier = None
            try:
                # WebKit returns NSNumber proxies; decode JSON into Python primitives.
                payload, error = NSJSONSerialization.dataWithJSONObject_options_error_(
                    message.body(), 0, None
                )
                if error or payload is None:
                    raise ValueError("Invalid native action payload")
                body = json.loads(bytes(payload))
                identifier = body.get("id") if isinstance(body, dict) else None
                source = str(message.frameInfo().request().URL().absoluteString())
                validate_bridge_message(
                    body, source, self.owner.base_url, message.frameInfo().isMainFrame()
                )
                data = None
                if body["action"] == "command":
                    command = json.loads(body["text"])
                    if not isinstance(command, dict) or not isinstance(
                        command.get("payload"), dict
                    ):
                        raise ValueError("Invalid desktop command")
                    if self.owner.command_handler is None:
                        raise ValueError("Desktop service is unavailable")
                    data = self.owner.command_handler(command.get("action"), command["payload"])
                elif body["action"] == "draft":
                    from src.shared.workspace_state import update

                    data = update({"draft": body["text"]})
                elif body["action"] == "phase":
                    self.owner.recording_phase = body["text"]
                elif body["action"] == "copy":
                    pasteboard = NSPasteboard.generalPasteboard()
                    pasteboard.clearContents()
                    if not pasteboard.setString_forType_(body["text"], NSStringPboardType):
                        raise RuntimeError("Clipboard could not be updated")
                else:
                    panel = NSSavePanel.savePanel()
                    panel.setNameFieldStringValue_("roastmyaudio-thoughts.txt")
                    panel.setTitle_("Export your thoughts")
                    if panel.runModal() != NSModalResponseOK:
                        raise RuntimeError("Export canceled")
                    Path(str(panel.URL().path())).write_text(body["text"], encoding="utf-8")
                response = {"id": identifier, "success": True, "data": data}
            except Exception as exc:
                response = {
                    "id": identifier,
                    "success": False,
                    "error": str(exc)
                    if isinstance(exc, ValueError)
                    else "Action canceled or unavailable. Your text is still in the workspace.",
                }
            self.owner.webview.evaluateJavaScript_completionHandler_(
                f"window.dispatchEvent(new CustomEvent('rma-native-response', {{detail: {json.dumps(response)}}}));",
                None,
            )

    types = {"RMAWorkspaceDelegate": RMAWorkspaceDelegate}
    for framework, names in [
        (
            AppKit,
            "NSApplication NSBackingStoreBuffered NSMakeRect NSViewHeightSizable NSViewWidthSizable NSWindow NSWindowStyleMaskClosable NSWindowStyleMaskMiniaturizable NSWindowStyleMaskResizable NSWindowStyleMaskTitled",
        ),
        (Foundation, "NSURL NSURLRequest"),
        (
            WebKit,
            "WKUserScript WKUserScriptInjectionTimeAtDocumentStart WKWebView WKWebViewConfiguration WKWebsiteDataStore",
        ),
    ]:
        types.update({name: getattr(framework, name) for name in names.split()})
    return types


class WorkspaceWindow:
    def __init__(self, base_url, persistent=True, command_handler=None):
        self.base_url = base_url
        self.command_handler = command_handler
        self.persistent = persistent
        self.recording_phase = "idle"
        self.native_busy = False
        self.window = None
        self.webview = None
        self._delegate = None
        self._types = None

    def show(self, view="dictation"):
        url = workspace_url(self.base_url, view)
        if self.window is None:
            types = self._types = _native_types()
            configuration = types["WKWebViewConfiguration"].alloc().init()
            if not self.persistent:
                configuration.setWebsiteDataStore_(
                    types["WKWebsiteDataStore"].nonPersistentDataStore()
                )
            script = (
                types["WKUserScript"]
                .alloc()
                .initWithSource_injectionTime_forMainFrameOnly_(
                    BRIDGE_SCRIPT
                    + f"\nwindow.roastmyaudioNativeBusy = {json.dumps(self.native_busy)};",
                    types["WKUserScriptInjectionTimeAtDocumentStart"],
                    True,
                )
            )
            configuration.userContentController().addUserScript_(script)
            self._delegate = types["RMAWorkspaceDelegate"].alloc().init()
            self._delegate.configure(self)
            configuration.userContentController().addScriptMessageHandler_name_(
                self._delegate, "roastmyaudio"
            )
            self.webview = (
                types["WKWebView"]
                .alloc()
                .initWithFrame_configuration_(types["NSMakeRect"](0, 0, 1180, 840), configuration)
            )
            self.webview.setAutoresizingMask_(
                types["NSViewWidthSizable"] | types["NSViewHeightSizable"]
            )
            self.webview.setNavigationDelegate_(self._delegate)
            self.webview.setUIDelegate_(self._delegate)
            style = (
                types["NSWindowStyleMaskTitled"]
                | types["NSWindowStyleMaskClosable"]
                | types["NSWindowStyleMaskMiniaturizable"]
                | types["NSWindowStyleMaskResizable"]
            )
            self.window = (
                types["NSWindow"]
                .alloc()
                .initWithContentRect_styleMask_backing_defer_(
                    types["NSMakeRect"](0, 0, 1180, 840),
                    style,
                    types["NSBackingStoreBuffered"],
                    False,
                )
            )
            self.window.setTitle_("RoastMyAudio · Your voice, in words")
            self.window.setMinSize_((740, 580))
            self.window.setReleasedWhenClosed_(False)
            self.window.setContentView_(self.webview)
            self.window.setDelegate_(self._delegate)
            self.window.center()
        current = str(self.webview.URL().absoluteString()) if self.webview.URL() else ""
        if current and same_origin(current, self.base_url):
            # Hash navigation preserves drafts and active recording state.
            self.webview.evaluateJavaScript_completionHandler_(
                f"location.hash = {json.dumps(view)};", None
            )
        else:
            self.webview.loadRequest_(
                self._types["NSURLRequest"].requestWithURL_(
                    self._types["NSURL"].URLWithString_(url)
                )
            )
        self.window.makeKeyAndOrderFront_(None)
        self._types["NSApplication"].sharedApplication().activateIgnoringOtherApps_(True)

    def dispatch(self, event, payload):
        if self.webview:
            self.webview.evaluateJavaScript_completionHandler_(
                f"window.dispatchEvent(new CustomEvent({json.dumps(event)}, {{detail: {json.dumps(payload)}}}));",
                None,
            )

    def set_native_busy(self, busy):
        self.native_busy = bool(busy)
        if self.webview:
            self.webview.evaluateJavaScript_completionHandler_(
                f"window.dispatchEvent(new CustomEvent('rma-native-busy', {{detail: {json.dumps(self.native_busy)}}}));",
                None,
            )

    def close(self):
        if self.window:
            self.webview.evaluateJavaScript_completionHandler_(
                "window.dispatchEvent(new Event('rma-workspace-shutdown'));", None
            )
            self.webview.stopLoading()
            # Replacing the document releases web media even during an asynchronous close.
            self.webview.loadHTMLString_baseURL_("", None)
            self.webview.configuration().userContentController().removeScriptMessageHandlerForName_(
                "roastmyaudio"
            )
            self.webview.setNavigationDelegate_(None)
            self.webview.setUIDelegate_(None)
            self.window.setDelegate_(None)
            self.window.close()
            self.window = self.webview = self._delegate = None
