using WordSearch.Api.Models;

namespace WordSearch.Api.Search;

public sealed class ScanStrategy : ISearchStrategy
{
    public string Name => "scan";

    public IReadOnlyList<string> SearchInFile(
        string lang, int nbCar,
        IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint,
        bool strict)
    {
        ValidateParams(lstCar, lstHint);
        var entries = WordBase.Load(lang, nbCar);
        var avail = BuildAvail(lstCar);
        var (availSet, availFreq) = BuildAvailStructures(avail, strict);
        bool emptyCars = IsEffectivelyEmpty(lstCar);
        bool emptyHints = HasNoCarHints(lstHint);

        var results = new List<string>();
        foreach (var entry in entries)
        {
            bool ok = (emptyCars || MatchesContent(entry.Normalized, availSet, availFreq, strict, entry.Freq))
                   && (emptyHints || MatchesHints(entry.Word, lstHint));
            if (ok) results.Add(entry.Word);
        }
        return results;
    }

    public static IReadOnlyList<string> ScanRange(
        IReadOnlyList<WordEntry> entries, int start, int end,
        IReadOnlyList<string>? lstCar, IReadOnlyList<Hint>? lstHint, bool strict,
        bool emptyCars, bool emptyHints,
        HashSet<string> availSet, byte[]? availFreq)
    {
        var results = new List<string>();
        for (int i = start; i < end; i++)
        {
            var entry = entries[i];
            bool ok = (emptyCars || MatchesContent(entry.Normalized, availSet, availFreq, strict, entry.Freq))
                   && (emptyHints || MatchesHints(entry.Word, lstHint));
            if (ok) results.Add(entry.Word);
        }
        return results;
    }

    public static bool MatchesContent(
        string normalized, HashSet<string> availSet,
        byte[]? availFreq, bool strict, byte[] wordFreq)
    {
        foreach (var c in normalized)
            if (!availSet.Contains(c.ToString()))
                return false;
        if (!strict) return true;
        for (int i = 0; i < 26; i++)
            if (wordFreq[i] > availFreq![i]) return false;
        return true;
    }

    public static bool MatchesHints(string word, IReadOnlyList<Hint>? hints)
    {
        if (hints == null) return true;
        foreach (var hint in hints)
        {
            if (string.IsNullOrEmpty(hint.Car)) continue;
            int idx = hint.Pos - 1;
            if (idx >= word.Length)
            {
                if (!hint.Inverted) return false;
                continue;
            }
            char wc = word[idx];
            char hc = hint.Car[0];
            if (hint.Inverted ? wc == hc : wc != hc) return false;
        }
        return true;
    }

    public static bool IsEffectivelyEmpty(IReadOnlyList<string>? lst) =>
        lst == null || lst.All(s => string.IsNullOrEmpty(s));

    public static bool HasNoCarHints(IReadOnlyList<Hint>? lst) =>
        lst == null || lst.All(h => string.IsNullOrEmpty(h.Car));

    public static void ValidateParams(IReadOnlyList<string>? lstCar, IReadOnlyList<Hint>? lstHint)
    {
        if (IsEffectivelyEmpty(lstCar) && HasNoCarHints(lstHint))
            throw new ArgumentException("lst_car and lst_hint cannot both be empty");
    }

    internal static List<string> BuildAvail(IReadOnlyList<string>? lstCar) =>
        lstCar?.Where(s => !string.IsNullOrEmpty(s)).ToList() ?? [];

    internal static (HashSet<string> availSet, byte[]? availFreq) BuildAvailStructures(
        List<string> avail, bool strict)
    {
        var availSet = new HashSet<string>(avail);
        byte[]? availFreq = null;
        if (strict)
        {
            availFreq = new byte[26];
            foreach (var s in avail)
            {
                var i = s[0] - 'a';
                if ((uint)i < 26) availFreq[i]++;
            }
        }
        return (availSet, availFreq);
    }
}
