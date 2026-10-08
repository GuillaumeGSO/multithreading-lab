
namespace WordSearch.Api.Search;

public sealed class ScanStrategy : ISearchStrategy
{
    public string Name => "scan";

    public IReadOnlyList<string> SearchInFile(
        string lang, int wordLength,
        IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints,
        bool strict)
    {
        ValidateParams(wordLength, letters, hints);
        var entries = WordBase.Load(lang, wordLength);
        var avail = BuildAvail(letters);
        var (availSet, availFreq) = BuildAvailStructures(avail, strict);
        bool emptyLetters = IsEffectivelyEmpty(letters);
        bool emptyHints = HasNoLetterHints(hints);

        var results = new List<string>();
        foreach (var entry in entries)
        {
            bool ok = (emptyLetters || MatchesContent(entry.Normalized, availSet, availFreq, strict, entry.Freq))
                   && (emptyHints || MatchesHints(entry.Word, hints));
            if (ok) results.Add(entry.Word);
        }
        return results;
    }

    public static IReadOnlyList<string> ScanRange(
        IReadOnlyList<WordEntry> entries, int start, int end,
        IReadOnlyList<string>? letters, IReadOnlyList<Hint>? hints, bool strict,
        bool emptyLetters, bool emptyHints,
        LetterSet availSet, byte[]? availFreq)
    {
        var results = new List<string>();
        for (int i = start; i < end; i++)
        {
            var entry = entries[i];
            bool ok = (emptyLetters || MatchesContent(entry.Normalized, availSet, availFreq, strict, entry.Freq))
                   && (emptyHints || MatchesHints(entry.Word, hints));
            if (ok) results.Add(entry.Word);
        }
        return results;
    }

    public static bool MatchesContent(
        string normalized, LetterSet availSet,
        byte[]? availFreq, bool strict, byte[] wordFreq)
    {
        foreach (var c in normalized)
            if (!availSet.Contains(c))
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
            if (string.IsNullOrEmpty(hint.Letter)) continue;
            int idx = hint.Position - 1;
            // Positions are 1-indexed: one below 1 is out of range like one past
            // the end (word[-1] would throw).
            if (idx < 0 || idx >= word.Length)
            {
                if (!hint.Excluded) return false;
                continue;
            }
            char wc = word[idx];
            char hc = hint.Letter[0];
            if (hint.Excluded ? wc == hc : wc != hc) return false;
        }
        return true;
    }

    public static bool IsEffectivelyEmpty(IReadOnlyList<string>? lst) =>
        lst == null || lst.All(s => string.IsNullOrEmpty(s));

    public static bool HasNoLetterHints(IReadOnlyList<Hint>? lst) =>
        lst == null || lst.All(h => string.IsNullOrEmpty(h.Letter));

    public static void ValidateParams(int wordLength, IReadOnlyList<string>? letters, IReadOnlyList<Hint>? hints)
    {
        if (wordLength <= 0 || (IsEffectivelyEmpty(letters) && HasNoLetterHints(hints)))
            throw new ArgumentException("letters and hints cannot both be empty");
    }

    internal static List<string> BuildAvail(IReadOnlyList<string>? letters) =>
        letters?.Where(s => !string.IsNullOrEmpty(s)).ToList() ?? [];

    internal static (LetterSet availSet, byte[]? availFreq) BuildAvailStructures(
        List<string> avail, bool strict)
    {
        var availSet = new LetterSet(avail);
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
