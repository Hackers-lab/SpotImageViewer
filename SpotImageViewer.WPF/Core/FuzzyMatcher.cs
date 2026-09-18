using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace SpotImageViewer.WPF.Core;

public static class FuzzyMatcher
{
    public static string NormalizeText(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return "";
        string upper = text.ToUpperInvariant();
        // Replace non-alphanumeric with spaces
        string cleaned = Regex.Replace(upper, @"[^A-Z0-9\s]", " ");
        // Collapse spaces
        return Regex.Replace(cleaned, @"\s+", " ").Trim();
    }

    public static string StripHonorifics(string text)
    {
        string norm = NormalizeText(text);
        string[] prefixes = { "C O ", "S O ", "D O ", "W O ", "CARE OF ", "LATE ", "LT ", "SRI ", "SMT ", "MD ", "MR ", "MRS ", "DR " };
        foreach (var p in prefixes)
        {
            if (norm.StartsWith(p))
            {
                norm = norm.Substring(p.Length).Trim();
            }
        }
        return norm;
    }

    public static double Similarity(string s1, string s2)
    {
        if (string.IsNullOrEmpty(s1) || string.IsNullOrEmpty(s2)) return 0.0;
        if (s1 == s2) return 1.0;

        int dist = LevenshteinDistance(s1, s2);
        int maxLen = Math.Max(s1.Length, s2.Length);
        return 1.0 - ((double)dist / maxLen);
    }

    public static int LevenshteinDistance(string s, string t)
    {
        int n = s.Length;
        int m = t.Length;
        int[,] d = new int[n + 1, m + 1];

        if (n == 0) return m;
        if (m == 0) return n;

        for (int i = 0; i <= n; d[i, 0] = i++) { }
        for (int j = 0; j <= m; d[0, j] = j++) { }

        for (int i = 1; i <= n; i++)
        {
            for (int j = 1; j <= m; j++)
            {
                int cost = (t[j - 1] == s[i - 1]) ? 0 : 1;
                d[i, j] = Math.Min(
                    Math.Min(d[i - 1, j] + 1, d[i, j - 1] + 1),
                    d[i - 1, j - 1] + cost);
            }
        }
        return d[n, m];
    }
}
