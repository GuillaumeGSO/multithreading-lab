
namespace WordSearch.Api.Search;

public sealed class ParallelSearchService
{
    private readonly SearchDispatcher _dispatcher = new();
    private readonly bool _parallel;
    private readonly int _splitDegree;

    public int SplitDegree => _splitDegree;

    public ParallelSearchService()
    {
        _parallel = !string.Equals(
            Environment.GetEnvironmentVariable("SEARCH_MODE"), "baseline",
            StringComparison.OrdinalIgnoreCase);
        _splitDegree = ParseSplitDegree();
    }

    // Public entry points used by the API endpoints
    public Task<IReadOnlyList<string>> SearchInFileAsync(
        string lang, int wordLength, IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints, bool strict)
    {
        if (_parallel)
            return FileSplitAsync(lang, wordLength, letters, hints, strict, _splitDegree);
        return Task.FromResult(_dispatcher.FileDispatch(lang, wordLength, letters, hints, strict));
    }

    public Task<IReadOnlyList<string>> SearchInManyAsync(
        string lang, string letters, IReadOnlyList<Hint>? hints)
    {
        if (_parallel)
            return ManyNestedAsync(lang, letters, hints, _splitDegree);
        return Task.FromResult(_dispatcher.ManyBaseline(lang, letters, hints));
    }

    // Axis B: intra-file split — used by bench and the parallel API path
    public async Task<IReadOnlyList<string>> FileSplitAsync(
        string lang, int wordLength, IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints, bool strict, int threads)
    {
        ScanStrategy.ValidateParams(wordLength, letters, hints);
        var entries = WordBase.Load(lang, wordLength);
        int n = Math.Max(1, Math.Min(threads, Math.Max(1, entries.Count)));
        if (n <= 1)
        {
            var avail = ScanStrategy.BuildAvail(letters);
            var (availSet, availFreq) = ScanStrategy.BuildAvailStructures(avail, strict);
            return ScanStrategy.ScanRange(entries, 0, entries.Count, letters, hints, strict,
                ScanStrategy.IsEffectivelyEmpty(letters), ScanStrategy.HasNoLetterHints(hints),
                availSet, availFreq);
        }

        bool emptyLetters = ScanStrategy.IsEffectivelyEmpty(letters);
        bool emptyHints = ScanStrategy.HasNoLetterHints(hints);
        var avail2 = ScanStrategy.BuildAvail(letters);
        var (availSet2, availFreq2) = ScanStrategy.BuildAvailStructures(avail2, strict);

        int chunk = (entries.Count + n - 1) / n;
        var tasks = new Task<IReadOnlyList<string>>[n];
        for (int i = 0; i < n; i++)
        {
            int s = Math.Min(i * chunk, entries.Count);
            int e = Math.Min(s + chunk, entries.Count);
            int s2 = s, e2 = e;
            tasks[i] = Task.Run(() => ScanStrategy.ScanRange(
                entries, s2, e2, letters, hints, strict,
                emptyLetters, emptyHints, availSet2, availFreq2));
        }
        var partials = await Task.WhenAll(tasks);
        var result = new List<string>();
        foreach (var p in partials) result.AddRange(p);
        return result;
    }

    // Axis A: per-length fan-out
    public async Task<IReadOnlyList<string>> ManyFanoutAsync(
        string lang, string letters, IReadOnlyList<Hint>? hints)
    {
        if (string.IsNullOrEmpty(letters)) throw new ArgumentException("letters cannot be empty");
        int minLen = SearchDispatcher.MinLength(hints);
        var lengths = Enumerable.Range(minLen, letters.Length - minLen + 1).Reverse().ToArray();
        var pool = letters.Select(c => c.ToString()).ToList();
        var tasks = lengths.Select(len =>
            Task.Run<IReadOnlyList<string>>(() =>
            {
                try { return SearchDispatcher.Scan.SearchInFile(lang, len, pool, hints, false); }
                catch (ArgumentException) { return Array.Empty<string>(); }
            })
        ).ToArray();
        var partials = await Task.WhenAll(tasks);
        var result = new List<string>();
        foreach (var p in partials) result.AddRange(p);
        return result;
    }

    // Axis A+B: per-length fan-out with intra-file split per length
    public async Task<IReadOnlyList<string>> ManyNestedAsync(
        string lang, string letters, IReadOnlyList<Hint>? hints, int threads)
    {
        if (string.IsNullOrEmpty(letters)) throw new ArgumentException("letters cannot be empty");
        int minLen = SearchDispatcher.MinLength(hints);
        var lengths = Enumerable.Range(minLen, letters.Length - minLen + 1).Reverse().ToArray();
        var pool = letters.Select(c => c.ToString()).ToList();
        var tasks = lengths.Select(len =>
            FileSplitAsync(lang, len, pool, hints, false, threads)
        ).ToArray();
        var partials = await Task.WhenAll(tasks);
        var result = new List<string>();
        foreach (var p in partials) result.AddRange(p);
        return result;
    }

    private static int ParseSplitDegree()
    {
        if (int.TryParse(Environment.GetEnvironmentVariable("SPLIT_DEGREE"), out int v))
            return Math.Max(1, v);
        return 2;
    }
}
