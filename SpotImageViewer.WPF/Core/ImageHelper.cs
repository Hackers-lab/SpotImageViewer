using System;
using System.IO;
using System.Windows.Media.Imaging;

namespace SpotImageViewer.WPF.Core;

public static class ImageHelper
{
    public static BitmapImage? LoadBitmapSafe(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            return null;

        try
        {
            var bitmap = new BitmapImage();
            bitmap.BeginInit();
            bitmap.CacheOption = BitmapCacheOption.OnLoad;
            bitmap.CreateOptions = BitmapCreateOptions.IgnoreColorProfile | BitmapCreateOptions.DelayCreation;
            bitmap.UriSource = new Uri(path, UriKind.Absolute);
            bitmap.EndInit();
            bitmap.Freeze(); // Freezes for cross-thread access and max GPU rendering performance
            return bitmap;
        }
        catch
        {
            // Fallback: Read byte array to avoid file locking entirely
            try
            {
                byte[] bytes = File.ReadAllBytes(path);
                using var stream = new MemoryStream(bytes);
                var bitmap = new BitmapImage();
                bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad;
                bitmap.StreamSource = stream;
                bitmap.EndInit();
                bitmap.Freeze();
                return bitmap;
            }
            catch
            {
                return null;
            }
        }
    }
}
