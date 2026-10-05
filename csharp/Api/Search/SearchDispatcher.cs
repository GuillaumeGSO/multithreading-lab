using WordSearch.Api.Models;

namespace WordSearch.Api.Search;

public sealed class SearchDispatcher
{
    public static readonly ScanStrategy Scan = new();
    public static readonly IndexedStrategy Indexed = new();

    public static bool HasPinned(IReadOnlyList<Hint>? hints) =>
        hints?.Any(h => !string.IsNullOrEmpty(h.Car) && !h.Inverted) ?? false;

    public IReadOnlyList<string> FileDispatch(
        string lang, int nbCar, IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint, bool strict)
    {
        ISearchStrategy strategy = HasPinned(lstHint) ? Indexed : Scan;
        return strategy.SearchInFile(lang, nbCar, lstCar, lstHint, strict);
    }

    public IReadOnlyList<string> FileBaseline(
        string lang, int nbCar, IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint, bool strict) =>
        Scan.SearchInFile(lang, nbCar, lstCar, lstHint, strict);

    public IReadOnlyList<string> FileIndexed(
        string lang, int nbCar, IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint, bool strict) =>
        Indexed.SearchInFile(lang, nbCar, lstCar, lstHint, strict);

    public IReadOnlyList<string> ManyBaseline(string lang, string cars, IReadOnlyList<Hint>? lstHint)
    {
        if (string.IsNullOrEmpty(cars))
            throw new ArgumentException("cars cannot be empty");
        int minLen = MinLength(lstHint);
        var result = new List<string>();
        for (int len = cars.Length; len >= minLen; len--)
        {
            try
            {
                result.AddRange(Scan.SearchInFile(lang, len, cars.Select(c => c.ToString()).ToList(), lstHint, false));
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
            if (!string.IsNullOrEmpty(h.Car) && !h.Inverted && h.Pos > min)
                min = h.Pos;
        return min;
    }
}
