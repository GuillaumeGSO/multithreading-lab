
namespace WordSearch.Api.Search;

public sealed class SearchDispatcher
{
    public static readonly ScanStrategy Scan = new();
    public static readonly IndexedStrategy Indexed = new();

    public static bool HasPinned(IReadOnlyList<Hint>? hints) =>
        hints?.Any(h => !string.IsNullOrEmpty(h.Letter) && !h.Excluded) ?? false;

    public IReadOnlyList<string> FileDispatch(
        string lang, int wordLength, IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints, bool strict)
    {
        ISearchStrategy strategy = HasPinned(hints) ? Indexed : Scan;
        return strategy.SearchInFile(lang, wordLength, letters, hints, strict);
    }

    public IReadOnlyList<string> FileBaseline(
        string lang, int wordLength, IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints, bool strict) =>
        Scan.SearchInFile(lang, wordLength, letters, hints, strict);

    public IReadOnlyList<string> FileIndexed(
        string lang, int wordLength, IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints, bool strict) =>
        Indexed.SearchInFile(lang, wordLength, letters, hints, strict);

    public IReadOnlyList<string> ManyBaseline(string lang, string letters, IReadOnlyList<Hint>? hints)
    {
        if (string.IsNullOrEmpty(letters))
            throw new ArgumentException("letters cannot be empty");
        int minLen = MinLength(hints);
        var result = new List<string>();
        for (int len = letters.Length; len >= minLen; len--)
        {
            try
            {
                result.AddRange(Scan.SearchInFile(lang, len, letters.Select(c => c.ToString()).ToList(), hints, false));
            }
            catch (ArgumentException) { }
        }
        return result;
    }

    public static int MinLength(IReadOnlyList<Hint>? hints)
    {
        if (hints == null) return 1;
        int min = 1;
        foreach (var h in hints)
            if (!string.IsNullOrEmpty(h.Letter) && !h.Excluded && h.Position > min)
                min = h.Position;
        return min;
    }
}
