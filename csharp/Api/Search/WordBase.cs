using System.Collections.Concurrent;
using System.Globalization;
using System.Text;

namespace WordSearch.Api.Search;

public readonly record struct WordEntry(string Word, string Normalized, byte[] Freq);

public static class WordBase
{
    private static readonly ConcurrentDictionary<string, IReadOnlyList<WordEntry>> Cache = new();

    private static readonly string AssetsRoot =
        Environment.GetEnvironmentVariable("ASSETS_ROOT")
        ?? Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "assets");

    public static IReadOnlyList<WordEntry> Load(string lang, int length) =>
        Cache.GetOrAdd($"{lang}/{length}", _ => Build(lang, length));

    private static IReadOnlyList<WordEntry> Build(string lang, int length)
    {
        var path = Path.Combine(AssetsRoot, lang, $"{length}.txt");
        if (!File.Exists(path)) return Array.Empty<WordEntry>();

        var lines = File.ReadAllLines(path, Encoding.UTF8);
        var entries = new List<WordEntry>(lines.Length);
        foreach (var line in lines)
        {
            var word = line.Trim();
            if (word.Length == 0) continue;
            var normalized = Normalize(word);
            entries.Add(new WordEntry(word, normalized, BuildFreq(normalized)));
        }
        return entries;
    }

    public static string Normalize(string s)
    {
        var nfd = s.Normalize(NormalizationForm.FormD);
        var sb = new StringBuilder(nfd.Length);
        foreach (var c in nfd)
            if (CharUnicodeInfo.GetUnicodeCategory(c) != UnicodeCategory.NonSpacingMark)
                sb.Append(c);
        return sb.ToString();
    }

    public static byte[] BuildFreq(string normalized)
    {
        var freq = new byte[26];
        foreach (var c in normalized)
        {
            var i = c - 'a';
            if ((uint)i < 26) freq[i]++;
        }
        return freq;
    }
}
