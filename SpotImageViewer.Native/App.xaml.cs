using System;
using System.Threading.Tasks;
using System.Windows;
using SpotImageViewer.Native.Core;

namespace SpotImageViewer.Native;

public partial class App : System.Windows.Application
{
    protected override void OnStartup(System.Windows.StartupEventArgs e)
    {
        AppDomain.CurrentDomain.UnhandledException += (s, args) =>
        {
            Logger.LogError("APP_CRASH", "AppDomain UnhandledException", args.ExceptionObject as Exception);
        };

        DispatcherUnhandledException += (s, args) =>
        {
            Logger.LogError("APP_CRASH", "DispatcherUnhandledException", args.Exception);
            args.Handled = true;
        };

        base.OnStartup(e);

        if (e.Args.Length > 0 && e.Args[0] == "--test")
        {
            Task.Run(async () =>
            {
                try
                {
                    Logger.Log("TEST", "=== VERIFICATION START ===");

                    // 1. Folders & AppInfo
                    Logger.Log("TEST", "[TEST 1] Testing Folder Accessibility & Image Counts...");
                    var appInfo = await Database.Instance.GetAppInfoAsync().ConfigureAwait(false);
                    Logger.Log("TEST", $"  TOTAL IMAGES: {appInfo.TotalImages:N0}");
                    Logger.Log("TEST", $"  AVAILABLE IMAGES: {appInfo.AvailableImages:N0}");
                    foreach (var f in appInfo.Folders)
                    {
                        Logger.Log("TEST", $"  FOLDER: {f.Path} | Accessible={f.Accessible} | Count={f.ImageCount:N0} | IsPrimary={f.IsPrimary}");
                    }

                    // 2. Images
                    Logger.Log("TEST", "[TEST 2] Testing Consumer Images (Offline Filtering)...");
                    var (prof, imgs) = await Database.Instance.GetConsumerImagesAsync("301248243").ConfigureAwait(false);
                    Logger.Log("TEST", $"  CONSUMER 301248243: Name={prof?.Name}, AccessibleImagesCount={imgs.Count}");
                    foreach (var img in imgs)
                    {
                        bool exists = System.IO.File.Exists(img.FullPath);
                        Logger.Log("TEST", $"    IMG: Date={img.DateFormatted} | File={img.Filename} | ExistsOnDisk={exists}");
                    }

                    // 3. Live OSD
                    Logger.Log("TEST", "[TEST 3] Testing Live OSD Fetch...");
                    var osd = await LiveOsdService.Instance.FetchLiveOsdAsync("301248243").ConfigureAwait(false);
                    Logger.Log("TEST", $"  LIVE OSD: Status={osd.Status}, ConnStatus={osd.ConnectionStatus}, Name={osd.Name}, Address={osd.Address}, Office={osd.Office}, ConnDate={osd.ConnDate}, DocType={osd.DocType}, TotalDues={osd.TotalDues}, OSD={osd.Osd}, LPSC={osd.Lpsc}");

                    Logger.Log("TEST", "=== VERIFICATION END ===");
                }
                catch (Exception testEx)
                {
                    Logger.LogError("TEST", "Test error", testEx);
                }
                finally
                {
                    Dispatcher.Invoke(() => Shutdown(0));
                }
            });
            return;
        }

        ShutdownMode = ShutdownMode.OnMainWindowClose;
        var mainWindow = new MainWindow();
        MainWindow = mainWindow;
        mainWindow.Show();
        Logger.Log("APP", "MainWindow displayed and message loop entered");
    }
}
