using System;
using System.Collections.Concurrent;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;

namespace SpotImageViewer.Native.Core;

public static class ImageProcessor
{
    private static readonly ConcurrentDictionary<string, string> _lruCache = new();
    private static readonly System.Collections.Generic.LinkedList<string> _lruKeys = new();
    private static readonly object _cacheLock = new();
    private const int MAX_CACHE_ITEMS = 50;

    private static readonly ConcurrentDictionary<string, DateTime> _offlineHosts = new(StringComparer.OrdinalIgnoreCase);

    public static bool IsHostReachable(string uncPath)
    {
        if (!uncPath.StartsWith(@"\\")) return true;
        var parts = uncPath.Split('\\', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0) return false;
        string host = parts[0];

        if (_offlineHosts.TryGetValue(host, out var expireTime))
        {
            if (DateTime.UtcNow < expireTime) return false;
            _offlineHosts.TryRemove(host, out _);
        }

        try
        {
            var task = Task.Run(() => Directory.Exists(@"\\" + host));
            if (task.Wait(250))
            {
                if (task.Result) return true;
            }
        }
        catch { }

        _offlineHosts[host] = DateTime.UtcNow.AddSeconds(90);
        Logger.LogWarning("IMAGE", $"Host '{host}' unreachable. Skipping for 90s.");
        return false;
    }

    public static async Task<string?> GetImageDataUriAsync(string filePath, int maxDim = 1400)
    {
        if (string.IsNullOrWhiteSpace(filePath)) return null;

        // 1. Fast local resolution for UNC paths: check if filename exists locally
        if (filePath.StartsWith(@"\\"))
        {
            string fname = Path.GetFileName(filePath);
            string localPath = Path.Combine(Config.IMAGE_FOLDER, fname);
            if (File.Exists(localPath))
            {
                filePath = localPath;
            }
            else if (!IsHostReachable(filePath))
            {
                return null; // Host is offline - return in 0ms!
            }
        }

        if (!File.Exists(filePath)) return null;

        DateTime lastWriteUtc = DateTime.MinValue;
        long fileLen = 0;
        try
        {
            var fi = new FileInfo(filePath);
            lastWriteUtc = fi.LastWriteTimeUtc;
            fileLen = fi.Length;
        }
        catch { }

        var cacheKey = $"{filePath}_{maxDim}_{lastWriteUtc.Ticks}";

        lock (_cacheLock)
        {
            if (_lruCache.TryGetValue(cacheKey, out var cachedUri))
            {
                return cachedUri;
            }
        }

        // Check disk cache
        string diskThumbPath = GetDiskCachePath(filePath, maxDim, lastWriteUtc.Ticks);
        if (File.Exists(diskThumbPath))
        {
            try
            {
                byte[] diskBytes = await File.ReadAllBytesAsync(diskThumbPath);
                string uri = "data:image/jpeg;base64," + Convert.ToBase64String(diskBytes);
                AddToMemoryCache(cacheKey, uri);
                return uri;
            }
            catch { }
        }

        // Fast path for viewing: If full image and reasonable size (< 1.5MB), return original bytes
        if (maxDim >= 1400 && fileLen > 0 && fileLen < 1_500_000)
        {
            try
            {
                byte[] rawBytes = await File.ReadAllBytesAsync(filePath);
                string uri = "data:image/jpeg;base64," + Convert.ToBase64String(rawBytes);
                AddToMemoryCache(cacheKey, uri);
                return uri;
            }
            catch { }
        }

        // Downscale / thumbnail generation via GDI+
        return await Task.Run(() =>
        {
            try
            {
                using var original = Image.FromFile(filePath);
                
                // EXIF orientation normalization
                NormalizeExifOrientation(original);

                int origW = original.Width;
                int origH = original.Height;
                int targetW = origW;
                int targetH = origH;

                if (origW > maxDim || origH > maxDim)
                {
                    if (origW >= origH)
                    {
                        targetW = maxDim;
                        targetH = (int)Math.Round((double)origH * maxDim / origW);
                    }
                    else
                    {
                        targetH = maxDim;
                        targetW = (int)Math.Round((double)origW * maxDim / origH);
                    }
                }

                using var bitmap = new Bitmap(targetW, targetH, PixelFormat.Format24bppRgb);
                using (var g = Graphics.FromImage(bitmap))
                {
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g.SmoothingMode = SmoothingMode.HighQuality;
                    g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                    g.CompositingQuality = CompositingQuality.HighQuality;
                    g.DrawImage(original, 0, 0, targetW, targetH);
                }

                using var ms = new MemoryStream();
                var encoder = GetEncoder(ImageFormat.Jpeg);
                var encoderParams = new EncoderParameters(1);
                encoderParams.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, (long)82);
                bitmap.Save(ms, encoder, encoderParams);

                byte[] compressedBytes = ms.ToArray();
                
                // Save to disk cache asynchronously
                _ = Task.Run(() =>
                {
                    try { File.WriteAllBytes(diskThumbPath, compressedBytes); } catch { }
                });

                string dataUri = "data:image/jpeg;base64," + Convert.ToBase64String(compressedBytes);
                AddToMemoryCache(cacheKey, dataUri);
                return dataUri;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ImageProcessor] Error processing {filePath}: {ex.Message}");
                return null;
            }
        });
    }

    private static void NormalizeExifOrientation(Image img)
    {
        const int ExifOrientationTag = 0x0112;
        if (!Array.Exists(img.PropertyIdList, p => p == ExifOrientationTag)) return;

        var prop = img.GetPropertyItem(ExifOrientationTag);
        if (prop?.Value == null || prop.Value.Length < 2) return;

        int orientation = BitConverter.ToUInt16(prop.Value, 0);
        switch (orientation)
        {
            case 2: img.RotateFlip(RotateFlipType.RotateNoneFlipX); break;
            case 3: img.RotateFlip(RotateFlipType.Rotate180FlipNone); break;
            case 4: img.RotateFlip(RotateFlipType.Rotate180FlipX); break;
            case 5: img.RotateFlip(RotateFlipType.Rotate90FlipX); break;
            case 6: img.RotateFlip(RotateFlipType.Rotate90FlipNone); break;
            case 7: img.RotateFlip(RotateFlipType.Rotate270FlipX); break;
            case 8: img.RotateFlip(RotateFlipType.Rotate270FlipNone); break;
        }
        img.RemovePropertyItem(ExifOrientationTag);
    }

    private static ImageCodecInfo GetEncoder(ImageFormat format)
    {
        var codecs = ImageCodecInfo.GetImageEncoders();
        foreach (var codec in codecs)
        {
            if (codec.FormatID == format.Guid) return codec;
        }
        return codecs[0];
    }

    private static string GetDiskCachePath(string filePath, int maxDim, long ticks)
    {
        using var md5 = MD5.Create();
        byte[] hash = md5.ComputeHash(Encoding.UTF8.GetBytes($"{filePath}_{maxDim}_{ticks}"));
        string hashStr = Convert.ToHexString(hash).ToLowerInvariant();
        return Path.Combine(Config.THUMB_CACHE_DIR, $"thumb_{hashStr}.jpg");
    }

    private static void AddToMemoryCache(string key, string dataUri)
    {
        lock (_cacheLock)
        {
            if (_lruCache.Count >= MAX_CACHE_ITEMS)
            {
                var oldest = _lruKeys.First?.Value;
                if (oldest != null)
                {
                    _lruKeys.RemoveFirst();
                    _lruCache.TryRemove(oldest, out _);
                }
            }
            _lruCache[key] = dataUri;
            _lruKeys.AddLast(key);
        }
    }
}
