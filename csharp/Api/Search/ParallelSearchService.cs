using WordSearch.Api.Models;

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
        string lang, int nbCar, IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint, bool strict)
    {
        if (_parallel)
            return FileSplitAsync(lang, nbCar, lstCar, lstHint, strict, _splitDegree);
        return Task.FromResult(_dispatcher.FileDispatch(lang, nbCar, lstCar, lstHint, strict));
    }

    public Task<IReadOnlyList<string>> SearchInManyAsync(
        string lang, string cars, IReadOnlyList<Hint>? lstHint)
    {
        if (_parallel)
            return ManyNestedAsync(lang, cars, lstHint, _splitDegree);
        return Task.FromResult(_dispatcher.ManyBaseline(lang, cars, lstHint));
    }

    // Axis B: intra-file split — used by bench and the parallel API path
    public async Task<IReadOnlyList<string>> FileSplitAsync(
        string lang, int nbCar, IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint, bool strict, int threads)
    {
        ScanStrategy.ValidateParams(lstCar, lstHint);
        var entries = WordBase.Load(lang, nbCar);
        int n = Math.Max(1, Math.Min(threads, Math.Max(1, entries.Count)));
        if (n <= 1)
        {
            var avail = ScanStrategy.BuildAvail(lstCar);
            var (availSet, availFreq) = ScanStrategy.BuildAvailStructures(avail, strict);
            return ScanStrategy.ScanRange(entries, 0, entries.Count, lstCar, lstHint, strict,
                ScanStrategy.IsEffectivelyEmpty(lstCar), ScanStrategy.HasNoCarHints(lstHint),
                availSet, availFreq);
        }

        bool emptyCars = ScanStrategy.IsEffectivelyEmpty(lstCar);
        bool emptyHints = ScanStrategy.HasNoCarHints(lstHint);
        var avail2 = ScanStrategy.BuildAvail(lstCar);
        var (availSet2, availFreq2) = ScanStrategy.BuildAvailStructures(avail2, strict);

        int chunk = (entries.Count + n - 1) / n;
        var tasks = new Task<IReadOnlyList<string>>[n];
        for (int i = 0; i < n; i++)
        {
            int s = Math.Min(i * chunk, entries.Count);
            int e = Math.Min(s + chunk, entries.Count);
            int s2 = s, e2 = e;
            tasks[i] = Task.Run(() => ScanStrategy.ScanRange(
                entries, s2, e2, lstCar, lstHint, strict,
                emptyCars, emptyHints, availSet2, availFreq2));
        }
        var partials = await Task.WhenAll(tasks);
        var result = new List<string>();
        foreach (var p in partials) result.AddRange(p);
        return result;
    }

    // Axis A: per-length fan-out
    public async Task<IReadOnlyList<string>> ManyFanoutAsync(
        string lang, string cars, IReadOnlyList<Hint>? lstHint)
    {
        if (string.IsNullOrEmpty(cars)) throw new ArgumentException("cars cannot be empty");
        int minLen = SearchDispatcher.MinLength(lstHint);
        var lengths = Enumerable.Range(minLen, cars.Length - minLen + 1).Reverse().ToArray();
        var lstCar = cars.Select(c => c.ToString()).ToList();
        var tasks = lengths.Select(len =>
            Task.Run<IReadOnlyList<string>>(() =>
            {
                try { return SearchDispatcher.Scan.SearchInFile(lang, len, lstCar, lstHint, false); }
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
        string lang, string cars, IReadOnlyList<Hint>? lstHint, int threads)
    {
        if (string.IsNullOrEmpty(cars)) throw new ArgumentException("cars cannot be empty");
        int minLen = SearchDispatcher.MinLength(lstHint);
        var lengths = Enumerable.Range(minLen, cars.Length - minLen + 1).Reverse().ToArray();
        var lstCar = cars.Select(c => c.ToString()).ToList();
        var tasks = lengths.Select(len =>
            FileSplitAsync(lang, len, lstCar, lstHint, false, threads)
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
