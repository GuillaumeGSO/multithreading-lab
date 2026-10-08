namespace WordSearch.Api.Search;

/// <summary>
/// The implementation the live API serves, chosen by <c>SEARCH_MODE</c>. Every
/// language in this lab gives the modes the same meaning:
/// <list type="bullet">
/// <item><c>baseline</c>: single-threaded scan (<c>/many</c> scans the lengths one after another).</item>
/// <item><c>parallel</c>: scan split into <c>SPLIT_DEGREE</c> chunks per file on the ThreadPool;
/// <c>/many</c> also fans out one task per length (the default).</item>
/// <item><c>indexed</c>: index dispatcher for <c>/file</c> (positional index when a pinned
/// hint exists, scan otherwise); <c>/many</c> is the single-threaded scan.</item>
/// </list>
/// </summary>
public enum SearchMode { Baseline, Parallel, Indexed }

public static class SearchModes
{
    public const SearchMode Default = SearchMode.Parallel;

    /// <summary>
    /// Parses a <c>SEARCH_MODE</c> value (null or blank means the default). An unknown
    /// value throws, so a typo fails at startup instead of silently serving a different mode.
    /// </summary>
    public static SearchMode Parse(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return Default;
        var name = value.Trim();
        // Enum.TryParse would also accept numbers ("1"), so match names only.
        foreach (var mode in Enum.GetValues<SearchMode>())
            if (string.Equals(mode.ToString(), name, StringComparison.OrdinalIgnoreCase))
                return mode;
        var expected = string.Join(", ", Enum.GetNames<SearchMode>().Select(n => n.ToLowerInvariant()));
        throw new InvalidOperationException($"unknown SEARCH_MODE '{name}'; expected one of {expected}");
    }
}
