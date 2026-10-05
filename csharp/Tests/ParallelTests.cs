using WordSearch.Api.Models;
using WordSearch.Api.Search;
using Xunit;

namespace WordSearch.Tests;

public class ParallelTests
{
    private static readonly string[] LstCar = { "e", "l", "i", "s", "a" };
    private static readonly Hint[] HintsPinned = { new Hint(1, "l") };
    private static readonly Hint[] HintsInverted = { new Hint(2, "a", Inverted: true) };
    private static readonly Hint[] HintsMixed = { new Hint(1, "l"), new Hint(3, "i", Inverted: true) };

    // ---------------------------------------------------------------------------
    // FileSplit byte-identical to baseline for split degrees 1..5
    // ---------------------------------------------------------------------------

    public static IEnumerable<object[]> SplitDegrees() =>
        Enumerable.Range(1, 5).Select(d => new object[] { d });

    [Theory]
    [MemberData(nameof(SplitDegrees))]
    public async Task FileSplit_ContentOnly_MatchesBaseline(int degree)
    {
        var svc = new ParallelSearchService();
        var baseline = new SearchDispatcher().FileBaseline("fr", 5, LstCar, null, false);
        var split = await svc.FileSplitAsync("fr", 5, LstCar, null, false, degree);
        Assert.Equal(baseline, split);
    }

    [Theory]
    [MemberData(nameof(SplitDegrees))]
    public async Task FileSplit_ContentStrict_MatchesBaseline(int degree)
    {
        var svc = new ParallelSearchService();
        var baseline = new SearchDispatcher().FileBaseline("fr", 5, LstCar, null, strict: true);
        var split = await svc.FileSplitAsync("fr", 5, LstCar, null, strict: true, degree);
        Assert.Equal(baseline, split);
    }

    [Theory]
    [MemberData(nameof(SplitDegrees))]
    public async Task FileSplit_HintOnly_MatchesBaseline(int degree)
    {
        var svc = new ParallelSearchService();
        var baseline = new SearchDispatcher().FileBaseline("fr", 5, null, HintsPinned, false);
        var split = await svc.FileSplitAsync("fr", 5, null, HintsPinned, false, degree);
        Assert.Equal(baseline, split);
    }

    [Theory]
    [MemberData(nameof(SplitDegrees))]
    public async Task FileSplit_Mixed_MatchesBaseline(int degree)
    {
        var svc = new ParallelSearchService();
        var baseline = new SearchDispatcher().FileBaseline("fr", 5, LstCar, HintsMixed, false);
        var split = await svc.FileSplitAsync("fr", 5, LstCar, HintsMixed, false, degree);
        Assert.Equal(baseline, split);
    }

    // ---------------------------------------------------------------------------
    // ManyFanout byte-identical to ManyBaseline
    // ---------------------------------------------------------------------------

    [Fact]
    public async Task ManyFanout_NoHints_MatchesBaseline()
    {
        var svc = new ParallelSearchService();
        var baseline = new SearchDispatcher().ManyBaseline("fr", "guillaume", null);
        var fanout = await svc.ManyFanoutAsync("fr", "guillaume", null);
        Assert.Equal(baseline, fanout);
    }

    [Fact]
    public async Task ManyFanout_WithPinnedHint_MatchesBaseline()
    {
        var svc = new ParallelSearchService();
        var hints = new[] { new Hint(4, "a") };
        var baseline = new SearchDispatcher().ManyBaseline("fr", "guillaume", hints);
        var fanout = await svc.ManyFanoutAsync("fr", "guillaume", hints);
        Assert.Equal(baseline, fanout);
    }

    [Fact]
    public async Task ManyFanout_WithInvertedHint_MatchesBaseline()
    {
        var svc = new ParallelSearchService();
        var hints = new[] { new Hint(1, "g", Inverted: true) };
        var baseline = new SearchDispatcher().ManyBaseline("fr", "guillaume", hints);
        var fanout = await svc.ManyFanoutAsync("fr", "guillaume", hints);
        Assert.Equal(baseline, fanout);
    }

    // ---------------------------------------------------------------------------
    // ManyNested byte-identical to ManyBaseline for split degrees 1..3
    // ---------------------------------------------------------------------------

    public static IEnumerable<object[]> NestedDegrees() =>
        Enumerable.Range(1, 3).Select(d => new object[] { d });

    [Theory]
    [MemberData(nameof(NestedDegrees))]
    public async Task ManyNested_NoHints_MatchesBaseline(int degree)
    {
        var svc = new ParallelSearchService();
        var baseline = new SearchDispatcher().ManyBaseline("fr", "guillaume", null);
        var nested = await svc.ManyNestedAsync("fr", "guillaume", null, degree);
        Assert.Equal(baseline, nested);
    }

    [Theory]
    [MemberData(nameof(NestedDegrees))]
    public async Task ManyNested_WithPinnedHint_MatchesBaseline(int degree)
    {
        var svc = new ParallelSearchService();
        var hints = new[] { new Hint(4, "a") };
        var baseline = new SearchDispatcher().ManyBaseline("fr", "guillaume", hints);
        var nested = await svc.ManyNestedAsync("fr", "guillaume", hints, degree);
        Assert.Equal(baseline, nested);
    }
}
