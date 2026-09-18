using System;
using System.Collections.Concurrent;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace SpotImageViewer.WPF.Core;

public class LiveOsdService
{
    private static readonly LiveOsdService _instance = new();
    public static LiveOsdService Instance => _instance;

    private readonly HttpClientHandler _handler;
    private readonly HttpClient _client;

    private static readonly ConcurrentDictionary<string, (DateTime timestamp, LiveOsdRecord record)> _cache = new();
    private static readonly TimeSpan CacheTtl = TimeSpan.FromMinutes(15);

    private const string BasePortalUrl = "https://portal.wbsedcl.in/webdynpro/resources/wbsedcl/noduesandoutstandingreport/OutstandingReport";

    public LiveOsdService()
    {
        _handler = new HttpClientHandler
        {
            CookieContainer = new CookieContainer(),
            UseCookies = true,
            AllowAutoRedirect = true,
            AutomaticDecompression = DecompressionMethods.All
        };
        _client = new HttpClient(_handler)
        {
            Timeout = TimeSpan.FromSeconds(25)
        };
        _client.DefaultRequestHeaders.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
        _client.DefaultRequestHeaders.Add("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8");
        _client.DefaultRequestHeaders.Add("Accept-Language", "en-US,en;q=0.9");
    }

    public async Task<LiveOsdRecord> FetchLiveOsdAsync(string consumerId, bool forceRefresh = false)
    {
        string cleanId = consumerId.Trim();
        if (!Regex.IsMatch(cleanId, @"^\d{9}$"))
        {
            return new LiveOsdRecord
            {
                ConsumerId = cleanId,
                Status = "Failed",
                ConnectionStatus = "Invalid Consumer ID"
            };
        }

        if (!forceRefresh && _cache.TryGetValue(cleanId, out var cachedItem))
        {
            if (DateTime.UtcNow - cachedItem.timestamp < CacheTtl)
            {
                var cachedRec = cachedItem.record;
                cachedRec.Cached = true;
                return cachedRec;
            }
            _cache.TryRemove(cleanId, out _);
        }

        var record = new LiveOsdRecord { ConsumerId = cleanId };

        try
        {
            string targetUrl = $"{BasePortalUrl}?consumerId={cleanId}";
            Logger.Log("OSD", $"Fetching live OSD portal for CID {cleanId}...");

            // Step 1: Initial GET Request
            var resp = await _client.GetAsync(targetUrl).ConfigureAwait(false);
            resp.EnsureSuccessStatusCode();
            byte[] contentBytes = await resp.Content.ReadAsByteArrayAsync().ConfigureAwait(false);

            // Handle SAP 0-byte cookie handshake
            if (contentBytes.Length == 0)
            {
                Logger.Log("OSD", "0-byte initial response from SAP, retrying after cookie handshake...");
                await Task.Delay(300).ConfigureAwait(false);
                resp = await _client.GetAsync(targetUrl).ConfigureAwait(false);
                resp.EnsureSuccessStatusCode();
                contentBytes = await resp.Content.ReadAsByteArrayAsync().ConfigureAwait(false);
            }

            // If direct PDF was returned
            if (contentBytes.Length > 4 && contentBytes[0] == 0x25 && contentBytes[1] == 0x50 && contentBytes[2] == 0x44 && contentBytes[3] == 0x46)
            {
                Logger.Log("OSD", $"Direct PDF payload received ({contentBytes.Length} bytes). Parsing...");
                ParsePdfContent(contentBytes, record);
                record.Cached = false;
                _cache[cleanId] = (DateTime.UtcNow, record);
                return record;
            }

            string html = Encoding.UTF8.GetString(contentBytes);

            // Step 2: Match SAP WebDynpro redirect window / PDF link
            var match = Regex.Match(html, @"openExternalWindow\([^,]+,\s*['""]([^'""]+?)['""]", RegexOptions.IgnoreCase);
            if (!match.Success)
                match = Regex.Match(html, @"openExternalWindow\([^)]*?['""]([^'""]*?\.pdf[^'""]*?)['""]", RegexOptions.IgnoreCase);
            if (!match.Success)
                match = Regex.Match(html, @"['""]([^'""]*?\.pdf(?:\?[^'""]*)?)['""]", RegexOptions.IgnoreCase);
            if (!match.Success)
                match = Regex.Match(html, @"href=['""]([^'""]+\.pdf[^'""]*)['""]", RegexOptions.IgnoreCase);
            if (!match.Success)
                match = Regex.Match(html, @"window\.open\(['""]([^'""]+?)['""]", RegexOptions.IgnoreCase);
            if (!match.Success)
                match = Regex.Match(html, @"location\.href\s*=\s*['""]([^'""]+?)['""]", RegexOptions.IgnoreCase);

            if (!match.Success)
            {
                Logger.LogWarning("OSD", "No PDF redirect link found in SAP portal HTML response.");
                record.Status = "Failed";
                record.ConnectionStatus = "Portal Unavailable";
                return record;
            }

            string rawRelUrl = match.Groups[1].Value;
            string decodedUrl = DecodeSapUrl(rawRelUrl);
            string pdfUrl = new Uri(new Uri(targetUrl), decodedUrl).ToString();

            Logger.Log("OSD", $"Fetching PDF stream from decoded URL: {pdfUrl}");

            // Step 3: Fetch the actual PDF stream WITH Referer header to prevent 403 Forbidden
            using var pdfReq = new HttpRequestMessage(HttpMethod.Get, pdfUrl);
            pdfReq.Headers.Add("Referer", targetUrl);
            pdfReq.Headers.Add("Accept", "application/pdf,application/octet-stream,*/*");

            var pdfResp = await _client.SendAsync(pdfReq).ConfigureAwait(false);
            pdfResp.EnsureSuccessStatusCode();

            byte[] pdfBytes = await pdfResp.Content.ReadAsByteArrayAsync().ConfigureAwait(false);
            if (pdfBytes.Length < 4 || pdfBytes[0] != 0x25 || pdfBytes[1] != 0x50 || pdfBytes[2] != 0x44 || pdfBytes[3] != 0x46)
            {
                Logger.LogWarning("OSD", $"Retrieved payload for {cleanId} does not have valid %PDF- magic bytes.");
                record.Status = "Failed";
                record.ConnectionStatus = "Invalid PDF";
                return record;
            }

            ParsePdfContent(pdfBytes, record);
            
            try
            {
                string pdfDir = Path.Combine(Path.GetTempPath(), "SpotImageViewer_OSD");
                if (!Directory.Exists(pdfDir)) Directory.CreateDirectory(pdfDir);
                string pdfPath = Path.Combine(pdfDir, $"{cleanId}_osd.pdf");
                File.WriteAllBytes(pdfPath, pdfBytes);
                record.PdfPath = pdfPath;
            }
            catch { }

            record.Cached = false;
            record.Status = "Success";
            _cache[cleanId] = (DateTime.UtcNow, record);
            Logger.Log("OSD", $"Successfully fetched and parsed Live OSD for {cleanId}: Status={record.ConnectionStatus}, TotalDues={record.TotalDues:F2}");
        }
        catch (Exception ex)
        {
            Logger.LogError("OSD", $"Error fetching Live OSD for {cleanId}", ex);
            record.Status = "Failed";
            record.ConnectionStatus = ex.Message.Contains("403") ? "Access Forbidden" : "Network Error";
        }

        return record;
    }

    private static string DecodeSapUrl(string rawUrl)
    {
        var decoded = Regex.Replace(rawUrl, @"\\x([0-9a-fA-F]{2})", m => ((char)Convert.ToInt32(m.Groups[1].Value, 16)).ToString());
        return decoded.Replace("&amp;", "&");
    }

    private void ParsePdfContent(byte[] pdfBytes, LiveOsdRecord record)
    {
        try
        {
            string text = ExtractTextFromPdf(pdfBytes);
            string upperText = text.ToUpperInvariant();

            // Document Type
            if (upperText.Contains("NO DUES CERTIFICATE"))
            {
                record.DocType = "NO DUES CERTIFICATE";
            }
            else if (upperText.Contains("OUTSTANDING REPORT"))
            {
                record.DocType = "OUTSTANDING REPORT";
            }
            else
            {
                record.DocType = "UNKNOWN";
            }

            // Consumer Name
            var nameMatch = Regex.Match(text, @"Name\s*:\s*([^\n\r]+)");
            if (nameMatch.Success) record.Name = nameMatch.Groups[1].Value.Trim();

            // Service Location Address
            var addrMatch = Regex.Match(text, @"Service Location Address\s*:\s*([\s\S]*?)(?=Office Name\s*:)", RegexOptions.IgnoreCase);
            if (addrMatch.Success)
            {
                record.Address = Regex.Replace(addrMatch.Groups[1].Value, @"\s+", " ").Trim();
            }

            // Office Name
            var offMatch = Regex.Match(text, @"Office Name\s*:\s*([^\n\r]+)");
            if (offMatch.Success) record.Office = offMatch.Groups[1].Value.Trim();

            // Date of Service Connection
            var connDateMatch = Regex.Match(text, @"Date of Service Connection\s*:\s*([^\n\r]+)");
            if (connDateMatch.Success) record.ConnDate = connDateMatch.Groups[1].Value.Trim();

            // Connection Status
            var statMatch = Regex.Match(text, @"Connection Status\s*:\s*([^\n\r]+?)(?=\s{2,}|Date of Service Connection|Office Name|\t|\n|\r|$)", RegexOptions.IgnoreCase);
            if (!statMatch.Success)
            {
                statMatch = Regex.Match(text, @"Connection Status\s*:\s*([^\n\r]+)", RegexOptions.IgnoreCase);
            }

            if (statMatch.Success)
            {
                string rawStat = statMatch.Groups[1].Value.Trim();
                record.ConnectionStatus = rawStat;
                string normStat = rawStat.ToUpperInvariant();

                record.IsDeemed = normStat.Contains("DEEMED");
                record.IsTempDisconnected = normStat.Contains("TEMP");
                record.IsDisconnected = !record.IsDeemed && !record.IsTempDisconnected && (normStat.Contains("DISCONNECT") || normStat.Contains("DISCONN"));
                record.IsLive = !record.IsDeemed && !record.IsDisconnected && !record.IsTempDisconnected && (normStat.Contains("LIVE") || Regex.IsMatch(normStat, @"\bCONNECTED\b"));
            }

            // Unpaid bill / OSD
            double osd = 0.0;
            var osdMatch = Regex.Match(text, @"total unpaid bill amount is Rs\.\s*([\d\.]+)", RegexOptions.IgnoreCase);
            if (osdMatch.Success && double.TryParse(osdMatch.Groups[1].Value, out var parsedOsd))
            {
                osd = parsedOsd;
            }
            else if (record.DocType == "NO DUES CERTIFICATE" || text.IndexOf("no unpaid bill", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                osd = 0.0;
            }
            record.Osd = osd;

            // LPSC
            double lpsc = 0.0;
            var lpscMatch = Regex.Match(text, @"Late Payment Surcharge \(LPSC\) amount of Rs\.\s*([\d\.]+)", RegexOptions.IgnoreCase);
            if (lpscMatch.Success && double.TryParse(lpscMatch.Groups[1].Value, out var parsedLpsc))
            {
                lpsc = parsedLpsc;
            }
            record.Lpsc = lpsc;

            record.TotalDues = Math.Round(record.Osd + record.Lpsc, 2);
            record.FileSizeKb = Math.Round(pdfBytes.Length / 1024.0, 1);
        }
        catch (Exception ex)
        {
            Logger.LogError("OSD", "Error parsing PDF text", ex);
        }
    }

    private static string ExtractTextFromPdf(byte[] pdfBytes)
    {
        var sb = new StringBuilder();
        string raw = Encoding.Latin1.GetString(pdfBytes);

        // Find all streams
        int curIdx = 0;
        while (true)
        {
            int streamStart = raw.IndexOf("stream", curIdx, StringComparison.Ordinal);
            if (streamStart < 0) break;
            streamStart += 6;
            if (streamStart < raw.Length && raw[streamStart] == '\r') streamStart++;
            if (streamStart < raw.Length && raw[streamStart] == '\n') streamStart++;

            int streamEnd = raw.IndexOf("endstream", streamStart, StringComparison.Ordinal);
            if (streamEnd < 0) break;

            int len = streamEnd - streamStart;
            if (len > 0 && streamStart + len <= pdfBytes.Length)
            {
                byte[] streamBytes = new byte[len];
                Buffer.BlockCopy(pdfBytes, streamStart, streamBytes, 0, len);

                try
                {
                    // Attempt zlib / deflate decompression
                    if (streamBytes.Length > 2 && streamBytes[0] == 0x78)
                    {
                        using var ms = new MemoryStream(streamBytes);
                        using var zs = new ZLibStream(ms, CompressionMode.Decompress);
                        using var outMs = new MemoryStream();
                        zs.CopyTo(outMs);
                        string decomp = Encoding.Latin1.GetString(outMs.ToArray());
                        ExtractTextObjects(decomp, sb);
                    }
                    else
                    {
                        string plain = Encoding.Latin1.GetString(streamBytes);
                        ExtractTextObjects(plain, sb);
                    }
                }
                catch
                {
                    try
                    {
                        // Fallback: raw deflate (skip 2-byte header)
                        if (streamBytes.Length > 2)
                        {
                            using var ms = new MemoryStream(streamBytes, 2, streamBytes.Length - 2);
                            using var ds = new DeflateStream(ms, CompressionMode.Decompress);
                            using var outMs = new MemoryStream();
                            ds.CopyTo(outMs);
                            string decomp = Encoding.Latin1.GetString(outMs.ToArray());
                            ExtractTextObjects(decomp, sb);
                        }
                    }
                    catch
                    {
                        string plain = Encoding.Latin1.GetString(streamBytes);
                        ExtractTextObjects(plain, sb);
                    }
                }
            }

            curIdx = streamEnd + 9;
        }

        return sb.ToString();
    }

    private static void ExtractTextObjects(string content, StringBuilder sb)
    {
        // Matches (text) Tj
        var matches = Regex.Matches(content, @"\(([^)]*)\)\s*Tj", RegexOptions.Singleline);
        foreach (Match m in matches)
        {
            sb.AppendLine(m.Groups[1].Value);
        }

        // Matches [(text)] TJ
        var arrayMatches = Regex.Matches(content, @"\[(.*?)\]\s*TJ", RegexOptions.Singleline);
        foreach (Match m in arrayMatches)
        {
            var inner = Regex.Matches(m.Groups[1].Value, @"\(([^)]*)\)");
            foreach (Match im in inner)
            {
                sb.Append(im.Groups[1].Value).Append(' ');
            }
            sb.AppendLine();
        }
    }
}
