using System;
using System.IO;

namespace SpotImageViewer.WPF.Core;

public static class Config
{
    public static readonly string BASE_DIR = @"C:\spotbillfiles\backup";
    public static readonly string IMAGE_FOLDER = Path.Combine(BASE_DIR, "image");
    public static readonly string DB_FILE = Path.Combine(BASE_DIR, "images_v7.db");
    public static readonly string THUMB_CACHE_DIR = Path.Combine(BASE_DIR, "thumb_cache");
    public static readonly string WEBVIEW_STORAGE = Path.Combine(BASE_DIR, "webview_storage_native");
    public static readonly string TARIFF_SETTINGS_FILE = Path.Combine(BASE_DIR, "tariff_settings.json");
    public static readonly string VERIFICATION_SESSION_FILE = Path.Combine(BASE_DIR, "verification_session.json");
    public const string CURRENT_VERSION = "0.0.1";
    public const string UPDATE_URL = "https://raw.githubusercontent.com/Hackers-lab/SpotImageViewer/refs/heads/main/update.json";

    public static string GetSafeWebViewStorage()
    {
        string dir = WEBVIEW_STORAGE;
        string lockFile = Path.Combine(dir, "EBWebView", "lockfile");
        if (File.Exists(lockFile))
        {
            try
            {
                using var fs = File.Open(lockFile, FileMode.Open, FileAccess.ReadWrite, FileShare.None);
            }
            catch
            {
                dir = Path.Combine(Path.GetTempPath(), "spot_webview_native_alt");
            }
        }
        if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
        return dir;
    }

    public const string DEFAULT_TARIFF_JSON = @"{
  ""Domestic (Rural) - Rate A(DM-R)"": {
    ""fixed_charge"": 30.0,
    ""min_charge"": 75.0,
    ""load_factor"": 0.5,
    ""slabs"": [
      {""limit"": 34, ""rate"": 5.00},
      {""limit"": 26, ""rate"": 6.24},
      {""limit"": 40, ""rate"": 6.89},
      {""limit"": 100, ""rate"": 7.44},
      {""limit"": 100, ""rate"": 7.61},
      {""limit"": null, ""rate"": 9.22}
    ],
    ""ed_slabs"": [{""limit"": 300, ""rate"": 0.0}, {""limit"": null, ""rate"": 0.10}]
  },
  ""Domestic (Urban) - Rate A(DM-U)"": {
    ""fixed_charge"": 30.0,
    ""min_charge"": 75.0,
    ""load_factor"": 0.5,
    ""slabs"": [
      {""limit"": 34, ""rate"": 5.04},
      {""limit"": 26, ""rate"": 6.33},
      {""limit"": 40, ""rate"": 7.12},
      {""limit"": 100, ""rate"": 7.52},
      {""limit"": 100, ""rate"": 7.69},
      {""limit"": null, ""rate"": 9.22}
    ],
    ""ed_slabs"": [{""limit"": 300, ""rate"": 0.0}, {""limit"": null, ""rate"": 0.10}]
  },
  ""Commercial - Rate A(CM)"": {
    ""fixed_charge"": 60.0,
    ""min_charge"": 105.0,
    ""load_factor"": 0.75,
    ""slabs"": [
      {""limit"": 60, ""rate"": 5.77},
      {""limit"": 40, ""rate"": 7.52},
      {""limit"": 50, ""rate"": 8.20},
      {""limit"": 150, ""rate"": 8.51},
      {""limit"": null, ""rate"": 9.02}
    ],
    ""ed_slabs"": [
      {""limit"": 150, ""rate"": 0.0},
      {""limit"": 500, ""rate"": 0.10},
      {""limit"": 1000, ""rate"": 0.125},
      {""limit"": null, ""rate"": 0.15}
    ]
  },
  ""Commercial - Rate A(CM-II)"": {
    ""fixed_charge"": 34.0,
    ""min_charge"": 105.0,
    ""load_factor"": 0.75,
    ""slabs"": [{""limit"": null, ""rate"": 6.09}],
    ""ed_slabs"": [
      {""limit"": 150, ""rate"": 0.0},
      {""limit"": 500, ""rate"": 0.10},
      {""limit"": 1000, ""rate"": 0.125},
      {""limit"": null, ""rate"": 0.15}
    ]
  },
  ""Agriculture Normal - Rate C(A)"": {
    ""fixed_charge"": 60.0,
    ""min_charge"": 60.0,
    ""load_factor"": 0.75,
    ""slabs"": [{""limit"": null, ""rate"": 4.66}],
    ""ed_slabs"": [{""limit"": null, ""rate"": 0.0}]
  },
  ""Agriculture TOD - Rate C(T)"": {
    ""fixed_charge"": 40.0,
    ""min_charge"": 40.0,
    ""load_factor"": 0.75,
    ""tod_slabs"": {""Normal"": 3.50, ""Peak"": 7.71, ""Off_Peak"": 2.65},
    ""ed_slabs"": [{""limit"": null, ""rate"": 0.0}]
  },
  ""Industry (Rural) - Rate B(I-R)"": {
    ""fixed_charge"": 75.0,
    ""min_charge"": 200.0,
    ""load_factor"": 0.75,
    ""slabs"": [
      {""limit"": 500, ""rate"": 5.07},
      {""limit"": null, ""rate"": 7.65}
    ],
    ""ed_slabs"": [
      {""limit"": 500, ""rate"": 0.0},
      {""limit"": 2000, ""rate"": 0.025},
      {""limit"": 3500, ""rate"": 0.075},
      {""limit"": null, ""rate"": 0.125}
    ]
  }
}";

    static Config()
    {
        try
        {
            if (!Directory.Exists(BASE_DIR)) Directory.CreateDirectory(BASE_DIR);
            if (!Directory.Exists(IMAGE_FOLDER)) Directory.CreateDirectory(IMAGE_FOLDER);
            if (!Directory.Exists(THUMB_CACHE_DIR)) Directory.CreateDirectory(THUMB_CACHE_DIR);
            if (!Directory.Exists(WEBVIEW_STORAGE)) Directory.CreateDirectory(WEBVIEW_STORAGE);
        }
        catch { }
    }
}
