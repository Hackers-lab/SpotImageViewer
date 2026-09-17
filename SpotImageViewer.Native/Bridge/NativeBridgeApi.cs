using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Forms;
using SpotImageViewer.Native.Core;
using Application = System.Windows.Application;

namespace SpotImageViewer.Native.Bridge;

[ComVisible(true)]
[ClassInterface(ClassInterfaceType.AutoDual)]
public class NativeBridgeApi
{
    private readonly Window _mainWindow;

    public NativeBridgeApi(Window mainWindow)
    {
        _mainWindow = mainWindow;
    }

    public async Task<string> Invoke(string methodName, string jsonArgs)
    {
        try
        {
            return await HandleInvokeAsync(methodName, jsonArgs).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            var err = ex.InnerException != null ? ex.InnerException.Message : ex.Message;
            Logger.LogError("BRIDGE", $"Method: {methodName}, Error: {err}", ex);
            return JsonSerializer.Serialize(new { success = false, error = err });
        }
    }

    private async Task<string> HandleInvokeAsync(string method, string jsonArgs)
    {
        using var doc = JsonDocument.Parse(string.IsNullOrWhiteSpace(jsonArgs) ? "[]" : jsonArgs);
        var args = doc.RootElement;

        switch (method)
        {
            // --- System & App Shell ---
            case "get_app_info":
            {
                var info = await Database.Instance.GetAppInfoAsync().ConfigureAwait(false);
                return JsonSerializer.Serialize(info);
            }
            case "get_theme":
            {
                var theme = await Database.Instance.GetDbInfoAsync("app_theme").ConfigureAwait(false)
                            ?? await Database.Instance.GetDbInfoAsync("theme").ConfigureAwait(false)
                            ?? "dark";
                return JsonSerializer.Serialize(new { success = true, theme = theme.Replace("\"", "").Trim() });
            }
            case "set_theme":
            {
                string theme = args.GetArrayLength() > 0 ? args[0].GetString() ?? "dark" : "dark";
                await Database.Instance.SetDbInfoAsync("app_theme", $"\"{theme}\"").ConfigureAwait(false);
                return JsonSerializer.Serialize(new { success = true, theme });
            }
            case "show_window":
            {
                Application.Current.Dispatcher.Invoke(() => _mainWindow.Show());
                return JsonSerializer.Serialize(new { success = true });
            }
            case "log_perf_client":
            {
                return JsonSerializer.Serialize(new { success = true });
            }
            case "open_url_external":
            {
                string url = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                if (!string.IsNullOrEmpty(url))
                {
                    Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
                }
                return JsonSerializer.Serialize(new { success = true });
            }
            case "open_file_external":
            {
                string path = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                if (File.Exists(path) || Directory.Exists(path))
                {
                    Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
                }
                return JsonSerializer.Serialize(new { success = true });
            }
            case "open_database_folder":
            {
                Process.Start(new ProcessStartInfo(Config.BASE_DIR) { UseShellExecute = true });
                return JsonSerializer.Serialize(new { success = true });
            }
            case "get_system_clipboard":
            {
                string clip = "";
                Application.Current.Dispatcher.Invoke(() =>
                {
                    try { clip = System.Windows.Clipboard.GetText(); } catch { }
                });
                return JsonSerializer.Serialize(new { success = true, text = clip });
            }
            case "check_for_updates":
            {
                return JsonSerializer.Serialize(new
                {
                    success = true,
                    has_update = false,
                    current_version = Config.CURRENT_VERSION,
                    latest_version = Config.CURRENT_VERSION,
                    release_notes = "Native Windows C# .NET 8 build active."
                });
            }

            // --- Viewer & Search ---
            case "search_consumer":
            {
                string query = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                string fType = args.GetArrayLength() > 1 ? args[1].GetString() ?? "auto" : "auto";
                var results = await Database.Instance.SearchConsumerAsync(query, fType).ConfigureAwait(false);
                return JsonSerializer.Serialize(new
                {
                    success = true,
                    detected_type = fType,
                    count = results.Count,
                    results
                });
            }
            case "get_consumer_images":
            {
                string cid = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                var (profile, images) = await Database.Instance.GetConsumerImagesAsync(cid).ConfigureAwait(false);

                if (images.Count == 0)
                {
                    return JsonSerializer.Serialize(new
                    {
                        success = false,
                        error = profile != null
                            ? "No accessible spot images found for this consumer (remote folder is offline)."
                            : "Consumer not found"
                    });
                }

                // Group by date
                var grouped = new Dictionary<string, List<ImageItem>>();
                var dates = new List<string>();
                foreach (var img in images)
                {
                    string dKey = string.IsNullOrEmpty(img.DateFormatted) ? "Unknown" : img.DateFormatted;
                    if (!grouped.ContainsKey(dKey))
                    {
                        grouped[dKey] = new List<ImageItem>();
                        dates.Add(dKey);
                    }
                    grouped[dKey].Add(img);
                }

                return JsonSerializer.Serialize(new
                {
                    success = true,
                    consumer_id = cid,
                    profile,
                    mru = profile?.Mru ?? (images.Count > 0 ? images[0].Mru : ""),
                    total_images = images.Count,
                    dates,
                    grouped,
                    images
                });
            }
            case "get_image_data":
            {
                string path = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                int maxDim = args.GetArrayLength() > 1 ? args[1].GetInt32() : 1400;
                string? dataUri = await ImageProcessor.GetImageDataUriAsync(path, maxDim).ConfigureAwait(false);
                if (dataUri != null)
                {
                    return JsonSerializer.Serialize(new { success = true, data = dataUri });
                }
                return JsonSerializer.Serialize(new { success = false, error = "File not found or unreadable" });
            }
            case "print_image":
            {
                string path = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                if (File.Exists(path))
                {
                    Process.Start(new ProcessStartInfo(path) { Verb = "print", UseShellExecute = true });
                    return JsonSerializer.Serialize(new { success = true });
                }
                return JsonSerializer.Serialize(new { success = false, error = "File not found" });
            }
            case "save_image_to":
            {
                string srcPath = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                string destPath = args.GetArrayLength() > 1 ? args[1].GetString() ?? "" : "";

                if (string.IsNullOrEmpty(destPath))
                {
                    destPath = PickSaveFile("Save Image", Path.GetFileName(srcPath), "JPEG Image (*.jpg)|*.jpg|All Files (*.*)|*.*");
                }

                if (!string.IsNullOrEmpty(destPath) && File.Exists(srcPath))
                {
                    File.Copy(srcPath, destPath, true);
                    return JsonSerializer.Serialize(new { success = true, path = destPath });
                }
                return JsonSerializer.Serialize(new { success = false, cancelled = string.IsNullOrEmpty(destPath) });
            }
            case "save_all_images":
            {
                string cid = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                string destDir = args.GetArrayLength() > 1 ? args[1].GetString() ?? "" : "";

                if (string.IsNullOrEmpty(destDir))
                {
                    destDir = PickFolder("Select Destination Folder");
                }

                if (!string.IsNullOrEmpty(destDir))
                {
                    var (_, images) = await Database.Instance.GetConsumerImagesAsync(cid).ConfigureAwait(false);
                    int count = 0;
                    foreach (var img in images)
                    {
                        if (File.Exists(img.FullPath))
                        {
                            string target = Path.Combine(destDir, img.Filename);
                            File.Copy(img.FullPath, target, true);
                            count++;
                        }
                    }
                    return JsonSerializer.Serialize(new { success = true, path = destDir, count });
                }
                return JsonSerializer.Serialize(new { success = false, cancelled = true });
            }
            case "get_search_history":
            {
                string key = args.GetArrayLength() > 0 ? args[0].GetString() ?? "consumer_ids" : "consumer_ids";
                var historyJson = await Database.Instance.GetDbInfoAsync("search_history").ConfigureAwait(false);
                var list = new List<string>();
                if (!string.IsNullOrEmpty(historyJson))
                {
                    try
                    {
                        using var hDoc = JsonDocument.Parse(historyJson);
                        if (hDoc.RootElement.TryGetProperty(key, out var arr))
                        {
                            foreach (var item in arr.EnumerateArray())
                            {
                                list.Add(item.GetString() ?? "");
                            }
                        }
                    }
                    catch { }
                }
                return JsonSerializer.Serialize(new { success = true, history = list });
            }
            case "save_search_history":
            {
                return JsonSerializer.Serialize(new { success = true });
            }
            case "get_consumer_note":
            {
                string cid = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                var (note, remarks) = await Database.Instance.GetConsumerNoteAsync(cid).ConfigureAwait(false);
                return JsonSerializer.Serialize(new { success = true, note, remarks });
            }
            case "save_consumer_note":
            {
                string cid = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                string note = args.GetArrayLength() > 1 ? args[1].GetString() ?? "" : "";
                string rem = args.GetArrayLength() > 2 ? args[2].GetString() ?? "" : "";
                await Database.Instance.SaveConsumerNoteAsync(cid, note, rem).ConfigureAwait(false);
                return JsonSerializer.Serialize(new { success = true });
            }
            case "delete_consumer_note":
            {
                string cid = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                await Database.Instance.DeleteConsumerNoteAsync(cid).ConfigureAwait(false);
                return JsonSerializer.Serialize(new { success = true });
            }

            // --- Calculators ---
            case "calculate_bill":
            {
                var payload = JsonSerializer.Deserialize<BillCalcPayload>(args[0].GetRawText());
                var result = BillingEngine.CalculateBill(payload ?? new BillCalcPayload());
                return JsonSerializer.Serialize(new { success = true, result });
            }
            case "calculate_theft_dual":
            {
                var payload = JsonSerializer.Deserialize<TheftDualPayload>(args[0].GetRawText());
                var (prov, finalRes, diffRs, diffPct) = BillingEngine.CalculateTheftDual(payload ?? new TheftDualPayload());
                return JsonSerializer.Serialize(new
                {
                    success = true,
                    provisional = prov,
                    @final = finalRes,
                    relief = new { diff_rs = diffRs, diff_pct = diffPct }
                });
            }
            case "calculate_theft_reverse_load":
            {
                var payload = JsonSerializer.Deserialize<ReverseLoadPayload>(args[0].GetRawText());
                var (loadKva, loadKw, gross, units) = BillingEngine.ReverseLoadSolver(payload ?? new ReverseLoadPayload());
                return JsonSerializer.Serialize(new
                {
                    success = true,
                    load_kva = loadKva,
                    load_kw = loadKw,
                    resulting_gross = gross,
                    assessed_units = units
                });
            }
            case "get_tariffs":
            {
                // 1. Try reading tariff_settings.json
                if (File.Exists(Config.TARIFF_SETTINGS_FILE))
                {
                    try
                    {
                        string json = await File.ReadAllTextAsync(Config.TARIFF_SETTINGS_FILE).ConfigureAwait(false);
                        using var tDoc = JsonDocument.Parse(json);
                        return JsonSerializer.Serialize(new { success = true, tariffs = tDoc.RootElement });
                    }
                    catch { }
                }
                
                // 2. Fallback to hardcoded verified default tariffs
                using var defDoc = JsonDocument.Parse(Config.DEFAULT_TARIFF_JSON);
                return JsonSerializer.Serialize(new { success = true, tariffs = defDoc.RootElement });
            }
            case "save_tariff_data":
            {
                try
                {
                    string tariffsJson = args.GetArrayLength() > 0 ? args[0].GetRawText() : "{}";
                    await File.WriteAllTextAsync(Config.TARIFF_SETTINGS_FILE, tariffsJson).ConfigureAwait(false);
                    return JsonSerializer.Serialize(new { success = true });
                }
                catch (Exception ex)
                {
                    return JsonSerializer.Serialize(new { success = false, error = ex.Message });
                }
            }
            case "reset_tariff_data":
            {
                try
                {
                    await File.WriteAllTextAsync(Config.TARIFF_SETTINGS_FILE, Config.DEFAULT_TARIFF_JSON).ConfigureAwait(false);
                    using var defDoc = JsonDocument.Parse(Config.DEFAULT_TARIFF_JSON);
                    return JsonSerializer.Serialize(new { success = true, tariffs = defDoc.RootElement });
                }
                catch (Exception ex)
                {
                    return JsonSerializer.Serialize(new { success = false, error = ex.Message });
                }
            }
            case "calculate_theft":
            {
                var payload = JsonSerializer.Deserialize<TheftDualPayload>(args[0].GetRawText());
                var (prov, finalRes, diffRs, diffPct) = BillingEngine.CalculateTheftDual(payload ?? new TheftDualPayload());
                return JsonSerializer.Serialize(new
                {
                    success = true,
                    provisional = prov,
                    @final = finalRes,
                    relief = new { diff_rs = diffRs, diff_pct = diffPct }
                });
            }

            // --- Live OSD ---
            case "get_live_osd":
            case "check_single_osd":
            {
                string cid = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                bool force = args.GetArrayLength() > 1 && args[1].GetBoolean();
                var data = await LiveOsdService.Instance.FetchLiveOsdAsync(cid, force).ConfigureAwait(false);
                return JsonSerializer.Serialize(new { success = true, data });
            }

            // --- Folder Management & Auto Indexing ---
            case "get_folder_status":
            {
                var folders = await Database.Instance.GetRegisteredFoldersAsync().ConfigureAwait(false);
                long available = folders.Where(f => f.Accessible).Sum(f => f.ImageCount);
                return JsonSerializer.Serialize(new { success = true, folders, available_images = available });
            }
            case "get_auto_index_settings":
            {
                return JsonSerializer.Serialize(new { success = true, mode = "manual" });
            }
            case "set_auto_index_settings":
            {
                return JsonSerializer.Serialize(new { success = true });
            }
            case "check_folder_changes":
            {
                return JsonSerializer.Serialize(new { success = true, has_changes = false, diff = 0 });
            }
            case "start_indexing":
            {
                return JsonSerializer.Serialize(new { success = true });
            }
            case "get_indexing_status":
            {
                return JsonSerializer.Serialize(new
                {
                    success = true,
                    is_indexing = false,
                    scanned = 0,
                    total = 0,
                    elapsed = 0,
                    speed = 0,
                    files_seen = 0,
                    new_added = 0
                });
            }
            case "get_note_options":
            {
                var opts = await Database.Instance.GetNoteOptionsAsync().ConfigureAwait(false);
                return JsonSerializer.Serialize(new { success = true, options = opts });
            }
            case "get_database_path":
            {
                return JsonSerializer.Serialize(new { success = true, path = Config.DB_FILE });
            }
            case "add_network_folder":
            {
                string folder = PickFolder("Select Image Folder to Add");
                if (!string.IsNullOrEmpty(folder))
                {
                    using var conn = Database.Instance.GetConnection();
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = "INSERT OR IGNORE INTO additional_folders (folder_path) VALUES (@p)";
                    cmd.Parameters.AddWithValue("@p", folder);
                    cmd.ExecuteNonQuery();
                    return JsonSerializer.Serialize(new { success = true, folder });
                }
                return JsonSerializer.Serialize(new { success = false, cancelled = true });
            }
            case "remove_network_folder":
            {
                string folder = args.GetArrayLength() > 0 ? args[0].GetString() ?? "" : "";
                using var conn = Database.Instance.GetConnection();
                using var cmd = conn.CreateCommand();
                cmd.CommandText = "DELETE FROM additional_folders WHERE folder_path = @p";
                cmd.Parameters.AddWithValue("@p", folder);
                cmd.ExecuteNonQuery();
                return JsonSerializer.Serialize(new { success = true });
            }

            // --- Audit Studio ---
            case "get_low_consumption_session":
            {
                if (File.Exists(Config.VERIFICATION_SESSION_FILE))
                {
                    string content = await File.ReadAllTextAsync(Config.VERIFICATION_SESSION_FILE).ConfigureAwait(false);
                    return JsonSerializer.Serialize(new { success = true, data = JsonDocument.Parse(content).RootElement });
                }
                return JsonSerializer.Serialize(new { success = true, data = new object[] { } });
            }
            case "save_low_consumption_session":
            {
                string dataJson = args.GetArrayLength() > 0 ? args[0].GetRawText() : "[]";
                await File.WriteAllTextAsync(Config.VERIFICATION_SESSION_FILE, dataJson).ConfigureAwait(false);
                return JsonSerializer.Serialize(new { success = true });
            }

            // --- Dialog Helpers ---
            case "pick_file":
            {
                string title = args.GetArrayLength() > 0 ? args[0].GetString() ?? "Select File" : "Select File";
                string res = PickFile(title, "All Files (*.*)|*.*");
                return JsonSerializer.Serialize(res);
            }
            case "pick_folder":
            {
                string title = args.GetArrayLength() > 0 ? args[0].GetString() ?? "Select Folder" : "Select Folder";
                string res = PickFolder(title);
                return JsonSerializer.Serialize(res);
            }

            // --- DCRC Billing Bridge Compatibility ---
            case "get_dcrc_defaults":
            {
                return JsonSerializer.Serialize(new
                {
                    success = true,
                    template_dir = Config.BASE_DIR,
                    zone_template = Path.Combine(Config.BASE_DIR, "Zones.xlsx"),
                    consumer_template = Path.Combine(Config.BASE_DIR, "Consumer Data.xlsx"),
                    default_output = Path.Combine(Config.BASE_DIR, "DCRC_OUTPUT"),
                    standard_rates = new { dc_1ph = 65, rc_1ph = 65, dr_1ph = 130, dc_3ph = 88, rc_3ph = 88, dr_3ph = 176 }
                });
            }
            case "pick_dcrc_events_files":
            case "pick_cash_payment_files":
            {
                var files = PickFilesMultiple("Select SAP Excel Files", "Excel Files (*.xls;*.xlsx)|*.xls;*.xlsx|All Files (*.*)|*.*");
                return JsonSerializer.Serialize(new { success = true, files, count = files.Count });
            }
            case "pick_zone_mapping_file":
            case "pick_consumer_master_file":
            {
                var file = PickFile("Select Excel File", "Excel Files (*.xlsx;*.xls)|*.xlsx;*.xls|All Files (*.*)|*.*");
                return JsonSerializer.Serialize(new { success = !string.IsNullOrEmpty(file), file });
            }
            case "pick_dcrc_output_folder":
            {
                var folder = PickFolder("Select DCRC Output Folder");
                return JsonSerializer.Serialize(new { success = !string.IsNullOrEmpty(folder), folder });
            }

            default:
                Logger.LogWarning("BRIDGE", $"Unhandled bridge method called: '{method}'");
                return JsonSerializer.Serialize(new { success = true, method, handled = "generic_stub" });
        }
    }

    private string PickFile(string title, string filter)
    {
        string chosen = "";
        Application.Current.Dispatcher.Invoke(() =>
        {
            using var ofd = new OpenFileDialog { Title = title, Filter = filter };
            if (ofd.ShowDialog() == DialogResult.OK)
            {
                chosen = ofd.FileName;
            }
        });
        return chosen;
    }

    private List<string> PickFilesMultiple(string title, string filter)
    {
        var list = new List<string>();
        Application.Current.Dispatcher.Invoke(() =>
        {
            using var ofd = new OpenFileDialog { Title = title, Filter = filter, Multiselect = true };
            if (ofd.ShowDialog() == DialogResult.OK)
            {
                list.AddRange(ofd.FileNames);
            }
        });
        return list;
    }

    private string PickSaveFile(string title, string defaultFilename, string filter)
    {
        string chosen = "";
        Application.Current.Dispatcher.Invoke(() =>
        {
            using var sfd = new SaveFileDialog { Title = title, FileName = defaultFilename, Filter = filter };
            if (sfd.ShowDialog() == DialogResult.OK)
            {
                chosen = sfd.FileName;
            }
        });
        return chosen;
    }

    private string PickFolder(string title)
    {
        string chosen = "";
        Application.Current.Dispatcher.Invoke(() =>
        {
            using var fbd = new FolderBrowserDialog { Description = title, UseDescriptionForTitle = true };
            if (fbd.ShowDialog() == DialogResult.OK)
            {
                chosen = fbd.SelectedPath;
            }
        });
        return chosen;
    }
}
