using System;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using SpotImageViewer.Native.Bridge;
using SpotImageViewer.Native.Core;

namespace SpotImageViewer.Native;

public partial class MainWindow : Window
{
    private NativeBridgeApi? _bridgeApi;

    public MainWindow()
    {
        InitializeComponent();
        Logger.Log("APP", "MainWindow instantiated");
        Loaded += MainWindow_Loaded;
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            Logger.Log("APP", "MainWindow Loaded event fired. Initializing WebView2...");
            await InitializeWebViewAsync();
        }
        catch (Exception ex)
        {
            Logger.LogError("APP", "Failed to initialize WebView2", ex);
            System.Windows.MessageBox.Show($"Failed to initialize WebView2: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async Task InitializeWebViewAsync()
    {
        // 1. Create CoreWebView2Environment with dedicated cache folder
        string storageDir = Config.GetSafeWebViewStorage();
        Logger.Log("WEBVIEW", $"Storage directory: {storageDir}");

        var env = await CoreWebView2Environment.CreateAsync(null, storageDir);
        await webView.EnsureCoreWebView2Async(env);
        Logger.Log("WEBVIEW", "CoreWebView2Environment ensured successfully");

        // 2. Configure WebView2 settings
        webView.CoreWebView2.Settings.IsWebMessageEnabled = true;
        webView.CoreWebView2.Settings.AreDevToolsEnabled = true;
        webView.CoreWebView2.Settings.IsStatusBarEnabled = false;

        // 3. Register Native Host Object & Bridge API
        _bridgeApi = new NativeBridgeApi(this);
        webView.CoreWebView2.AddHostObjectToScript("nativeApi", _bridgeApi);

        // 4. Register WebMessage listener for ultra-robust concurrent message-based RPC
        webView.CoreWebView2.WebMessageReceived += (sender, e) =>
        {
            string rawMsg = e.WebMessageAsJson;
            _ = Task.Run(async () =>
            {
                int id = -1;
                string method = "";
                try
                {
                    using var doc = JsonDocument.Parse(rawMsg);
                    var root = doc.RootElement;

                    // Handle JS Console forwarding
                    if (root.TryGetProperty("type", out var typeProp) && typeProp.GetString() == "__log")
                    {
                        string level = root.TryGetProperty("level", out var lProp) ? lProp.GetString() ?? "LOG" : "LOG";
                        string msg = root.TryGetProperty("msg", out var mProp) ? mProp.GetString() ?? "" : "";
                        Logger.Log($"JS_{level}", msg);
                        return;
                    }

                    id = root.GetProperty("id").GetInt32();
                    method = root.GetProperty("method").GetString() ?? "";
                    string argsJson = root.GetProperty("args").GetRawText();

                    Logger.Log("RPC_REQ", $"id={id}, method={method}, args={argsJson}");

                    string resultJson = await _bridgeApi.Invoke(method, argsJson).ConfigureAwait(false);

                    string preview = resultJson.Length > 120 ? resultJson.Substring(0, 120) + "..." : resultJson;
                    Logger.Log("RPC_RES", $"id={id}, method={method}, res={preview}");

                    await Dispatcher.InvokeAsync(() =>
                    {
                        try
                        {
                            webView.CoreWebView2.PostWebMessageAsJson($"{{\"id\":{id},\"result\":{resultJson}}}");
                        }
                        catch (Exception postEx)
                        {
                            Logger.LogError("RPC_POST", $"Failed to post result for id={id}, method={method}", postEx);
                        }
                    });
                }
                catch (Exception ex)
                {
                    Logger.LogError("RPC_ERR", $"Error handling message: {rawMsg}", ex);
                    if (id != -1)
                    {
                        await Dispatcher.InvokeAsync(() =>
                        {
                            try
                            {
                                var errPayload = JsonSerializer.Serialize(new { id, error = ex.Message });
                                webView.CoreWebView2.PostWebMessageAsJson(errPayload);
                            }
                            catch { }
                        });
                    }
                }
            });
        };

        // 5. Locate UI Directory
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string uiFolder = Path.Combine(baseDir, "UI");
        if (!Directory.Exists(uiFolder))
        {
            string devUi = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "SpotImageViewer.Native", "UI"));
            if (Directory.Exists(devUi))
            {
                uiFolder = devUi;
            }
        }
        Logger.Log("UI", $"Resolved UI folder: {uiFolder}");

        // 6. Map UI directory to virtual secure origin https://app.local
        webView.CoreWebView2.SetVirtualHostNameToFolderMapping(
            "app.local",
            uiFolder,
            CoreWebView2HostResourceAccessKind.Allow
        );

        // 7. Inject PyWebView compatibility polyfill script BEFORE document load
        const string polyfillScript = @"
            (function() {
                let _reqId = 0;
                const _pending = new Map();

                // Pipe console output to native logger
                const _oLog = console.log, _oWarn = console.warn, _oErr = console.error;
                function _sendConsole(level, args) {
                    try {
                        const msg = Array.from(args).map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ');
                        window.chrome.webview.postMessage({ type: '__log', level: level, msg: msg });
                    } catch(e) {}
                }
                console.log = function(...args) { _oLog.apply(console, args); _sendConsole('LOG', args); };
                console.warn = function(...args) { _oWarn.apply(console, args); _sendConsole('WARN', args); };
                console.error = function(...args) { _oErr.apply(console, args); _sendConsole('ERR', args); };

                window.chrome.webview.addEventListener('message', function(event) {
                    try {
                        const data = event.data;
                        if (data && _pending.has(data.id)) {
                            const p = _pending.get(data.id);
                            _pending.delete(data.id);
                            if (data.error) p.reject(new Error(data.error));
                            else p.resolve(data.result);
                        }
                    } catch (e) {
                        console.error('Error handling webview response:', e);
                    }
                });

                window.pywebview = {
                    api: new Proxy({}, {
                        get: function(target, prop) {
                            return function(...args) {
                                return new Promise(function(resolve, reject) {
                                    const curId = ++_reqId;
                                    _pending.set(curId, { resolve: resolve, reject: reject });
                                    window.chrome.webview.postMessage({ id: curId, method: prop, args: args });
                                });
                            };
                        }
                    })
                };
                
                // Signal ready
                window.dispatchEvent(new Event('pywebviewready'));
                document.dispatchEvent(new Event('pywebviewready'));
            })();
        ";

        await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(polyfillScript);

        webView.NavigationCompleted += WebView_NavigationCompleted;
        Logger.Log("NAV", "Navigating to https://app.local/index.html");
        webView.CoreWebView2.Navigate("https://app.local/index.html");
    }

    private async void WebView_NavigationCompleted(object? sender, CoreWebView2NavigationCompletedEventArgs e)
    {
        Logger.Log("NAV", $"Navigation completed. IsSuccess={e.IsSuccess}, WebErrorStatus={e.WebErrorStatus}");
        if (e.IsSuccess)
        {
            await webView.CoreWebView2.ExecuteScriptAsync(@"
                if (typeof window.safeInitApp === 'function') {
                    window.safeInitApp();
                }
                if (typeof window.lucide !== 'undefined' && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            ");
        }
    }
}
