using System;
using System.IO;

namespace SpotImageViewer.WPF.Core;

public static class Logger
{
    private static readonly object _lock = new();
    private static readonly string _logFile1;
    private static readonly string _logFile2;

    static Logger()
    {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        _logFile1 = Path.Combine(baseDir, "app.log");
        _logFile2 = @"c:\Users\Pramod\Documents\GitHub\SpotImageViewer\app_wpf.log";

        try
        {
            var dir2 = Path.GetDirectoryName(_logFile2);
            if (!string.IsNullOrEmpty(dir2) && !Directory.Exists(dir2))
            {
                Directory.CreateDirectory(dir2);
            }
            File.WriteAllText(_logFile1, $"[INIT] Logger started at {DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}\n");
            File.WriteAllText(_logFile2, $"[INIT] Logger started at {DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}\n");
        }
        catch { }
    }

    public static void Log(string tag, string message)
    {
        string line = $"[{DateTime.Now:HH:mm:ss.fff}] [{tag}] {message}";
        Console.WriteLine(line);

        lock (_lock)
        {
            try { File.AppendAllText(_logFile1, line + Environment.NewLine); } catch { }
            try { File.AppendAllText(_logFile2, line + Environment.NewLine); } catch { }
        }
    }

    public static void LogWarning(string tag, string message)
    {
        string line = $"[{DateTime.Now:HH:mm:ss.fff}] [WARN] [{tag}] {message}";
        Console.WriteLine(line);

        lock (_lock)
        {
            try { File.AppendAllText(_logFile1, line + Environment.NewLine); } catch { }
            try { File.AppendAllText(_logFile2, line + Environment.NewLine); } catch { }
        }
    }

    public static void LogError(string tag, string message, Exception? ex = null)
    {
        string line = $"[{DateTime.Now:HH:mm:ss.fff}] [ERROR] [{tag}] {message} {(ex != null ? ex.ToString() : "")}";
        Console.WriteLine(line);

        lock (_lock)
        {
            try { File.AppendAllText(_logFile1, line + Environment.NewLine); } catch { }
            try { File.AppendAllText(_logFile2, line + Environment.NewLine); } catch { }
        }
    }
}
