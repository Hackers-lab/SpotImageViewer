using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;

namespace SpotImageViewer.Native.Core;

public class Database
{
    private static readonly Database _instance = new();
    public static Database Instance => _instance;

    private readonly string _connectionString;

    public Database()
    {
        _connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = Config.DB_FILE,
            Mode = SqliteOpenMode.ReadOnly,
            DefaultTimeout = 5
        }.ToString();
    }

    public SqliteConnection GetConnection()
    {
        var conn = new SqliteConnection(_connectionString);
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            PRAGMA synchronous=NORMAL;
            PRAGMA cache_size=-16000;
            PRAGMA temp_store=MEMORY;
        ";
        try { cmd.ExecuteNonQuery(); } catch { }
        return conn;
    }

    public async Task<string?> GetDbInfoAsync(string key)
    {
        try
        {
            using var conn = GetConnection();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT value FROM db_info WHERE key = @key";
            cmd.Parameters.AddWithValue("@key", key);
            var res = await cmd.ExecuteScalarAsync().ConfigureAwait(false);
            return res?.ToString();
        }
        catch { return null; }
    }

    public async Task SetDbInfoAsync(string key, string value)
    {
        try
        {
            var rwBuilder = new SqliteConnectionStringBuilder
            {
                DataSource = Config.DB_FILE,
                Mode = SqliteOpenMode.ReadWrite,
                DefaultTimeout = 5
            };
            using var conn = new SqliteConnection(rwBuilder.ToString());
            await conn.OpenAsync().ConfigureAwait(false);
            using var cmd = conn.CreateCommand();
            cmd.CommandText = @"
                INSERT INTO db_info (key, value) VALUES (@key, @value)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            ";
            cmd.Parameters.AddWithValue("@key", key);
            cmd.Parameters.AddWithValue("@value", value);
            await cmd.ExecuteNonQueryAsync().ConfigureAwait(false);
        }
        catch { }
    }

    public async Task<AppInfoResponse> GetAppInfoAsync()
    {
        var info = new AppInfoResponse();
        try
        {
            using var conn = GetConnection();

            // Read cached image count
            var cachedImgStr = await GetDbInfoAsync("cached_total_images").ConfigureAwait(false)
                               ?? await GetDbInfoAsync("total_images_count").ConfigureAwait(false);

            if (!string.IsNullOrEmpty(cachedImgStr))
            {
                var clean = cachedImgStr.Trim('"', ' ', '\t', '\r', '\n');
                if (long.TryParse(clean, out var cachedImg))
                {
                    info.TotalImages = cachedImg;
                }
            }

            // Read cached consumer count
            var cachedConsStr = await GetDbInfoAsync("cached_consumer_count").ConfigureAwait(false)
                                ?? await GetDbInfoAsync("consumer_count").ConfigureAwait(false);

            if (!string.IsNullOrEmpty(cachedConsStr))
            {
                var cleanCons = cachedConsStr.Trim('"', ' ', '\t', '\r', '\n');
                if (long.TryParse(cleanCons, out var cachedCons))
                {
                    info.ConsumerCount = cachedCons;
                }
            }

            // Fallback for TotalImages if missing or 0
            if (info.TotalImages <= 0)
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = "SELECT MAX(ROWID) FROM images";
                var r = await cmd.ExecuteScalarAsync().ConfigureAwait(false);
                if (r != null && r != DBNull.Value && long.TryParse(r.ToString(), out var maxId) && maxId > 0)
                {
                    info.TotalImages = maxId;
                    _ = SetDbInfoAsync("cached_total_images", maxId.ToString());
                }
            }

            // Fallback for ConsumerCount if missing or 0
            if (info.ConsumerCount <= 0)
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = "SELECT COUNT(*) FROM meter_mapping";
                var r = await cmd.ExecuteScalarAsync().ConfigureAwait(false);
                if (r != null && r != DBNull.Value && long.TryParse(r.ToString(), out var maxCons) && maxCons > 0)
                {
                    info.ConsumerCount = maxCons;
                    _ = SetDbInfoAsync("cached_consumer_count", maxCons.ToString());
                }
            }

            info.HasMeterData = info.ConsumerCount > 0;
            info.ConsumerUpdatedAt = await GetDbInfoAsync("consumer_updated_at").ConfigureAwait(false)
                                     ?? await GetDbInfoAsync("consumer_data_updated_at").ConfigureAwait(false)
                                     ?? "";

            // Theme (matches app_theme key in Python SQLite)
            var themeVal = await GetDbInfoAsync("app_theme").ConfigureAwait(false)
                           ?? await GetDbInfoAsync("theme").ConfigureAwait(false)
                           ?? "\"dark\"";
            info.Theme = themeVal.Replace("\"", "").Trim();

            // Folders list (instant optimistic load - never blocks on UNC paths)
            info.Folders = await GetRegisteredFoldersAsync(conn).ConfigureAwait(false);
            info.AvailableImages = info.Folders.Where(f => f.Accessible).Sum(f => f.ImageCount);
            Logger.Log("DB", $"AppInfo loaded: {info.TotalImages:N0} images (available: {info.AvailableImages:N0}), {info.ConsumerCount:N0} consumers, theme={info.Theme}");
        }
        catch (Exception ex)
        {
            Logger.LogError("DB", "GetAppInfoAsync error", ex);
        }
        return info;
    }

    public static async Task<bool> ValidatePathAccessibilityAsync(string path, int timeoutMs = 350)
    {
        if (string.IsNullOrWhiteSpace(path)) return false;

        // Local drive: C:, D:, etc.
        if (path.Length >= 2 && path[1] == ':')
        {
            try
            {
                return Directory.Exists(path);
            }
            catch
            {
                return false;
            }
        }

        // Network UNC path: \\host\share\...
        if (path.StartsWith(@"\\"))
        {
            if (!ImageProcessor.IsHostReachable(path))
            {
                return false;
            }

            try
            {
                using var cts = new System.Threading.CancellationTokenSource(timeoutMs);
                var checkTask = Task.Run(() => Directory.Exists(path), cts.Token);
                return await checkTask.WaitAsync(TimeSpan.FromMilliseconds(timeoutMs)).ConfigureAwait(false);
            }
            catch
            {
                return false;
            }
        }

        try
        {
            return Directory.Exists(path);
        }
        catch
        {
            return false;
        }
    }

    public static string NormalizePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return "";
        return path.Trim().Replace('/', '\\').TrimEnd('\\');
    }

    public async Task<List<FolderItem>> GetRegisteredFoldersAsync(SqliteConnection? conn = null, bool validateAccessibility = true)
    {
        var list = new List<FolderItem>();
        bool dispose = false;
        if (conn == null)
        {
            conn = GetConnection();
            dispose = true;
        }

        try
        {
            list.Add(new FolderItem
            {
                Path = Config.IMAGE_FOLDER,
                IsPrimary = true,
                Accessible = Directory.Exists(Config.IMAGE_FOLDER)
            });

            using (var cmd = conn.CreateCommand())
            {
                cmd.CommandText = "SELECT folder_path FROM additional_folders";
                using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                var additionalPaths = new List<string>();
                while (await reader.ReadAsync().ConfigureAwait(false))
                {
                    additionalPaths.Add(reader.GetString(0));
                }

                if (validateAccessibility)
                {
                    var validationTasks = additionalPaths.Select(async p =>
                    {
                        bool acc = await ValidatePathAccessibilityAsync(p).ConfigureAwait(false);
                        return new FolderItem
                        {
                            Path = p,
                            IsPrimary = false,
                            Accessible = acc
                        };
                    }).ToList();

                    var results = await Task.WhenAll(validationTasks).ConfigureAwait(false);
                    list.AddRange(results);
                }
                else
                {
                    foreach (var p in additionalPaths)
                    {
                        list.Add(new FolderItem
                        {
                            Path = p,
                            IsPrimary = false,
                            Accessible = true
                        });
                    }
                }
            }

            // Aggregate image counts by directory from SQLite
            var dirCounts = new List<(string DirPath, long Count)>();
            try
            {
                using var countCmd = conn.CreateCommand();
                countCmd.CommandText = @"
                    SELECT d.dir_path, COUNT(i.rowid)
                    FROM directories d
                    LEFT JOIN images i ON i.dir_id = d.id
                    GROUP BY d.id";
                using var countReader = await countCmd.ExecuteReaderAsync().ConfigureAwait(false);
                while (await countReader.ReadAsync().ConfigureAwait(false))
                {
                    string dirPath = countReader.IsDBNull(0) ? "" : countReader.GetString(0);
                    long count = countReader.IsDBNull(1) ? 0 : countReader.GetInt64(1);
                    if (!string.IsNullOrWhiteSpace(dirPath) && count > 0)
                    {
                        dirCounts.Add((NormalizePath(dirPath), count));
                    }
                }
            }
            catch (Exception ex)
            {
                Logger.LogError("DB", "Error querying directory image counts", ex);
            }

            // Match directory counts to registered folders (prefix matching)
            foreach (var folder in list)
            {
                string normFolder = NormalizePath(folder.Path);
                if (string.IsNullOrEmpty(normFolder)) continue;

                long total = 0;
                foreach (var (dirPath, count) in dirCounts)
                {
                    if (dirPath.Equals(normFolder, StringComparison.OrdinalIgnoreCase) ||
                        dirPath.StartsWith(normFolder + "\\", StringComparison.OrdinalIgnoreCase))
                    {
                        total += count;
                    }
                }
                folder.ImageCount = total;
            }
        }
        catch (Exception ex)
        {
            Logger.LogError("DB", "GetRegisteredFoldersAsync error", ex);
        }
        finally
        {
            if (dispose) conn?.Dispose();
        }
        return list;
    }

    public async Task<List<ConsumerProfile>> SearchConsumerAsync(string query, string filterType = "auto")
    {
        var results = new List<ConsumerProfile>();
        query = query.Trim();
        if (string.IsNullOrWhiteSpace(query)) return results;

        if (filterType == "auto")
        {
            if (query.Length == 9 && Regex.IsMatch(query, @"^\d+$"))
                filterType = "cid";
            else if (query.Length == 10 && Regex.IsMatch(query, @"^\d+$"))
                filterType = "mobile";
            else if (Regex.IsMatch(query, @"[a-zA-Z]") && !Regex.IsMatch(query, @"\d") && query.Length >= 2)
                filterType = "name";
            else
                filterType = "meter";
        }

        try
        {
            using var conn = GetConnection();

            if (filterType == "cid")
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = @"
                    SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                    FROM meter_mapping WHERE consumer_id = @cid LIMIT 1";
                cmd.Parameters.AddWithValue("@cid", query);
                using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                if (await reader.ReadAsync().ConfigureAwait(false))
                {
                    results.Add(ReadProfile(reader));
                }
                else
                {
                    // Fallback stub profile so photos can still be viewed
                    results.Add(new ConsumerProfile
                    {
                        ConsumerId = query,
                        MeterNo = "",
                        Name = "",
                        Address = "",
                        MobileNumber = "",
                        ContractualLoad = "",
                        Class = "",
                        Mru = ""
                    });
                }
            }
            else if (filterType == "meter")
            {
                // 1. Try exact meter match
                using (var cmd = conn.CreateCommand())
                {
                    cmd.CommandText = @"
                        SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                        FROM meter_mapping WHERE meter_no = @m LIMIT 1";
                    cmd.Parameters.AddWithValue("@m", query);
                    using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                    if (await reader.ReadAsync().ConfigureAwait(false))
                    {
                        results.Add(ReadProfile(reader));
                    }
                }

                // 2. Try prefix meter match
                if (results.Count == 0)
                {
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = @"
                        SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                        FROM meter_mapping WHERE meter_no LIKE @m LIMIT 50";
                    cmd.Parameters.AddWithValue("@m", query + "%");
                    using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                    while (await reader.ReadAsync().ConfigureAwait(false))
                    {
                        results.Add(ReadProfile(reader));
                    }
                }

                // 3. Fallback: try LIKE %query% on meter_no
                if (results.Count == 0)
                {
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = @"
                        SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                        FROM meter_mapping WHERE meter_no LIKE @m LIMIT 50";
                    cmd.Parameters.AddWithValue("@m", "%" + query + "%");
                    using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                    while (await reader.ReadAsync().ConfigureAwait(false))
                    {
                        results.Add(ReadProfile(reader));
                    }
                }

                // 4. Also if query is numeric, check if it's a partial consumer_id prefix
                if (results.Count == 0 && Regex.IsMatch(query, @"^\d+$"))
                {
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = @"
                        SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                        FROM meter_mapping WHERE consumer_id LIKE @cid LIMIT 50";
                    cmd.Parameters.AddWithValue("@cid", query + "%");
                    using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                    while (await reader.ReadAsync().ConfigureAwait(false))
                    {
                        results.Add(ReadProfile(reader));
                    }
                }
            }
            else if (filterType == "mobile")
            {
                using var cmd = conn.CreateCommand();
                cmd.CommandText = @"
                    SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                    FROM meter_mapping WHERE mobile_number LIKE @q LIMIT 50";
                cmd.Parameters.AddWithValue("@q", query + "%");
                using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                while (await reader.ReadAsync().ConfigureAwait(false))
                {
                    results.Add(ReadProfile(reader));
                }
            }
            else // name
            {
                try
                {
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = @"
                        SELECT m.consumer_id, m.meter_no, m.name, m.address, m.mobile_number, m.contractual_load, m.class, m.mru, m.conn_phase
                        FROM meter_mapping_fts fts
                        JOIN meter_mapping m ON m.rowid = fts.rowid
                        WHERE meter_mapping_fts MATCH @q
                        ORDER BY rank LIMIT 50";
                    cmd.Parameters.AddWithValue("@q", $"\"{query}\"*");
                    using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                    while (await reader.ReadAsync().ConfigureAwait(false))
                    {
                        results.Add(ReadProfile(reader));
                    }
                }
                catch
                {
                    // Fallback to LIKE NOCASE
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = @"
                        SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                        FROM meter_mapping WHERE name LIKE @q COLLATE NOCASE LIMIT 50";
                    cmd.Parameters.AddWithValue("@q", "%" + query + "%");
                    using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
                    while (await reader.ReadAsync().ConfigureAwait(false))
                    {
                        results.Add(ReadProfile(reader));
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Logger.LogError("DB", $"SearchConsumerAsync error (query='{query}')", ex);
        }

        return results;
    }

    private static ConsumerProfile ReadProfile(Microsoft.Data.Sqlite.SqliteDataReader reader)
    {
        return new ConsumerProfile
        {
            ConsumerId = reader.IsDBNull(0) ? "" : reader.GetString(0),
            MeterNo = reader.IsDBNull(1) ? "" : reader.GetString(1),
            Name = reader.IsDBNull(2) ? "" : reader.GetString(2),
            Address = reader.IsDBNull(3) ? "" : reader.GetString(3),
            MobileNumber = reader.IsDBNull(4) ? "" : reader.GetString(4),
            ContractualLoad = reader.IsDBNull(5) ? "" : reader.GetString(5),
            Class = reader.IsDBNull(6) ? "" : reader.GetString(6),
            Mru = reader.IsDBNull(7) ? "" : reader.GetString(7),
            ConnPhase = reader.IsDBNull(8) ? 1 : reader.GetInt32(8)
        };
    }

    public async Task<(ConsumerProfile? profile, List<ImageItem> images)> GetConsumerImagesAsync(string consumerId)
    {
        consumerId = consumerId.Trim();
        ConsumerProfile? profile = null;
        var images = new List<ImageItem>();

        try
        {
            using var conn = GetConnection();

            // 1. Get profile
            using (var pCmd = conn.CreateCommand())
            {
                pCmd.CommandText = @"
                    SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class, mru, conn_phase
                    FROM meter_mapping WHERE consumer_id = @cid LIMIT 1";
                pCmd.Parameters.AddWithValue("@cid", consumerId);
                using var pReader = await pCmd.ExecuteReaderAsync().ConfigureAwait(false);
                if (await pReader.ReadAsync().ConfigureAwait(false))
                {
                    profile = ReadProfile(pReader);
                }
            }

            // 2. Get images with directory join matching Python's query
            var rawRows = new List<(string cid, string dateOrig, string dateIso, string mru, string filename, int dirId, string dirPath)>();
            using (var imgCmd = conn.CreateCommand())
            {
                imgCmd.CommandText = @"
                    SELECT i.consumer_id, i.date_original, i.date_iso, i.mru, i.filename, i.dir_id, d.dir_path
                    FROM images i 
                    JOIN directories d ON i.dir_id = d.id 
                    WHERE i.consumer_id = @cid 
                    ORDER BY i.date_iso DESC, CASE WHEN d.dir_path LIKE '_:%' THEN 0 ELSE 1 END, i.rowid ASC";
                imgCmd.Parameters.AddWithValue("@cid", consumerId);

                using var reader = await imgCmd.ExecuteReaderAsync().ConfigureAwait(false);
                while (await reader.ReadAsync().ConfigureAwait(false))
                {
                    rawRows.Add((
                        reader.GetString(0),
                        reader.IsDBNull(1) ? "" : reader.GetString(1),
                        reader.IsDBNull(2) ? "" : reader.GetString(2),
                        reader.IsDBNull(3) ? "" : reader.GetString(3),
                        reader.GetString(4),
                        reader.IsDBNull(5) ? 0 : reader.GetInt32(5),
                        reader.IsDBNull(6) ? Config.IMAGE_FOLDER : reader.GetString(6)
                    ));
                }
            }

            // Deduplicate by billing date and prefer local drive copies (matching Python's viewer_bridge.py)
            var byDate = new Dictionary<string, List<(string cid, string dateOrig, string dateIso, string mru, string filename, int dirId, string dirPath)>>();
            foreach (var r in rawRows)
            {
                string key = !string.IsNullOrEmpty(r.dateOrig) ? r.dateOrig : (!string.IsNullOrEmpty(r.dateIso) ? r.dateIso : "unknown");
                if (!byDate.ContainsKey(key))
                {
                    byDate[key] = new List<(string cid, string dateOrig, string dateIso, string mru, string filename, int dirId, string dirPath)>();
                }
                byDate[key].Add(r);
            }

            foreach (var kvp in byDate)
            {
                var candidates = kvp.Value;
                (string cid, string dateOrig, string dateIso, string mru, string filename, int dirId, string dirPath)? accessibleCandidate = null;
                string accessibleFullPath = "";

                // Check candidates: prioritize local drive copies over UNC network paths
                var orderedCandidates = candidates.OrderBy(c => c.dirPath.StartsWith(@"\\") ? 1 : 0).ToList();

                foreach (var c in orderedCandidates)
                {
                    string targetDir = c.dirPath;
                    string candidateFullPath = Path.Combine(targetDir, c.filename);

                    // 1. If path is UNC, check if filename exists locally in Config.IMAGE_FOLDER
                    if (targetDir.StartsWith(@"\\"))
                    {
                        string localCopy = Path.Combine(Config.IMAGE_FOLDER, c.filename);
                        if (File.Exists(localCopy))
                        {
                            accessibleCandidate = c;
                            accessibleFullPath = localCopy;
                            break;
                        }

                        // Host reachability check
                        if (!ImageProcessor.IsHostReachable(targetDir))
                        {
                            continue;
                        }

                        try
                        {
                            if (File.Exists(candidateFullPath))
                            {
                                accessibleCandidate = c;
                                accessibleFullPath = candidateFullPath;
                                break;
                            }
                        }
                        catch { }
                    }
                    else
                    {
                        // Local path
                        try
                        {
                            if (File.Exists(candidateFullPath))
                            {
                                accessibleCandidate = c;
                                accessibleFullPath = candidateFullPath;
                                break;
                            }
                        }
                        catch { }
                    }
                }

                // If no candidate exists or is accessible, DO NOT include this image or date!
                if (accessibleCandidate == null)
                {
                    continue;
                }

                var chosen = accessibleCandidate.Value;
                var formatted = chosen.dateIso;
                if (!string.IsNullOrEmpty(chosen.dateOrig) && chosen.dateOrig.Length == 8)
                {
                    // DDMMYYYY -> DD-MM-YYYY
                    formatted = $"{chosen.dateOrig.Substring(0, 2)}-{chosen.dateOrig.Substring(2, 2)}-{chosen.dateOrig.Substring(4, 4)}";
                }

                images.Add(new ImageItem
                {
                    ConsumerId = chosen.cid,
                    DateOriginal = chosen.dateOrig,
                    DateIso = chosen.dateIso,
                    DateFormatted = formatted,
                    Mru = chosen.mru,
                    Filename = chosen.filename,
                    DirId = chosen.dirId,
                    FullPath = accessibleFullPath,
                    Exists = true
                });
            }
        }
        catch (Exception ex)
        {
            Logger.LogError("DB", $"GetConsumerImagesAsync error (cid='{consumerId}')", ex);
        }

        return (profile, images);
    }

    public async Task<(string? note, string? remarks)> GetConsumerNoteAsync(string consumerId)
    {
        try
        {
            using var conn = GetConnection();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT note, remarks FROM notes WHERE consumer_id = @cid";
            cmd.Parameters.AddWithValue("@cid", consumerId);
            using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
            if (await reader.ReadAsync().ConfigureAwait(false))
            {
                return (
                    reader.IsDBNull(0) ? null : reader.GetString(0),
                    reader.IsDBNull(1) ? null : reader.GetString(1)
                );
            }
        }
        catch { }
        return (null, null);
    }

    public async Task SaveConsumerNoteAsync(string consumerId, string note, string remarks)
    {
        try
        {
            var rwBuilder = new SqliteConnectionStringBuilder
            {
                DataSource = Config.DB_FILE,
                Mode = SqliteOpenMode.ReadWrite,
                DefaultTimeout = 5
            };
            using var conn = new SqliteConnection(rwBuilder.ToString());
            await conn.OpenAsync().ConfigureAwait(false);
            using var cmd = conn.CreateCommand();
            cmd.CommandText = @"
                INSERT INTO notes (consumer_id, note, remarks) VALUES (@cid, @note, @rem)
                ON CONFLICT(consumer_id) DO UPDATE SET note = excluded.note, remarks = excluded.remarks;
            ";
            cmd.Parameters.AddWithValue("@cid", consumerId);
            cmd.Parameters.AddWithValue("@note", note);
            cmd.Parameters.AddWithValue("@rem", remarks);
            await cmd.ExecuteNonQueryAsync().ConfigureAwait(false);
        }
        catch { }
    }

    public async Task DeleteConsumerNoteAsync(string consumerId)
    {
        try
        {
            var rwBuilder = new SqliteConnectionStringBuilder
            {
                DataSource = Config.DB_FILE,
                Mode = SqliteOpenMode.ReadWrite,
                DefaultTimeout = 5
            };
            using var conn = new SqliteConnection(rwBuilder.ToString());
            await conn.OpenAsync().ConfigureAwait(false);
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "DELETE FROM notes WHERE consumer_id = @cid";
            cmd.Parameters.AddWithValue("@cid", consumerId);
            await cmd.ExecuteNonQueryAsync().ConfigureAwait(false);
        }
        catch { }
    }

    public async Task<List<string>> GetNoteOptionsAsync()
    {
        var opts = new List<string>();
        try
        {
            using var conn = GetConnection();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT option_text FROM note_options";
            using var reader = await cmd.ExecuteReaderAsync().ConfigureAwait(false);
            while (await reader.ReadAsync().ConfigureAwait(false))
            {
                if (!reader.IsDBNull(0)) opts.Add(reader.GetString(0));
            }
        }
        catch { }
        if (opts.Count == 0)
        {
            opts.AddRange(new[] { "OK", "CHECK", "RECHECK" });
        }
        return opts;
    }
}
