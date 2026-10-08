using WordSearch.Api.Search;
using Xunit;

namespace WordSearch.Tests;

/// <summary>
/// SEARCH_MODE: every mode returns exactly the baseline's words, and an unknown
/// mode is rejected (the application would fail at startup).
/// </summary>
public class SearchModeTests
{
    public static TheoryData<SearchMode> Modes => new(Enum.GetValues<SearchMode>());

    [Theory]
    [MemberData(nameof(Modes))]
    public async Task ModesMatchBaseline(SearchMode mode)
    {
        var baseline = new ParallelSearchService(SearchMode.Baseline);
        var svc = new ParallelSearchService(mode);
        string[] elisa = ["e", "l", "i", "s", "a"];
        var fileCases = new (int Length, string[] Letters, Hint[] Hints, bool Strict)[]
        {
            (5, elisa, [], true),
            (5, elisa, [new Hint(1, "s")], false),
            (7, [], [new Hint(1, "a"), new Hint(7, "e", Excluded: true)], false),
        };
        foreach (var c in fileCases)
        {
            var expected = await baseline.SearchInFileAsync("fr", c.Length, c.Letters, c.Hints, c.Strict);
            Assert.NotEmpty(expected);
            Assert.Equal(expected, await svc.SearchInFileAsync("fr", c.Length, c.Letters, c.Hints, c.Strict));
        }
        foreach (var (letters, hints) in new[] { ("guillaume", Array.Empty<Hint>()), ("artes", [new Hint(1, "a")]) })
        {
            var expected = await baseline.SearchInManyAsync("fr", letters, hints);
            Assert.NotEmpty(expected);
            Assert.Equal(expected, await svc.SearchInManyAsync("fr", letters, hints));
        }
    }

    [Theory]
    [InlineData(null, SearchMode.Parallel)]
    [InlineData(" ", SearchMode.Parallel)]
    [InlineData(" Indexed ", SearchMode.Indexed)]
    [InlineData("baseline", SearchMode.Baseline)]
    public void ParseAcceptsKnownModesInAnyCase(string? value, SearchMode expected) =>
        Assert.Equal(expected, SearchModes.Parse(value));

    [Theory]
    [InlineData("dispatcher")]
    [InlineData("1")]
    public void ParseRejectsUnknownModes(string value) =>
        Assert.Throws<InvalidOperationException>(() => SearchModes.Parse(value));
}
