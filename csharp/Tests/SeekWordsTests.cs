using WordSearch.Api.Search;
using Xunit;

namespace WordSearch.Tests;

public class SeekWordsTests
{
    // ---------------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------------

    [Theory]
    [InlineData(null, true)]
    [InlineData(new string[0], true)]
    [InlineData(new[] { "" }, true)]
    [InlineData(new[] { "a" }, false)]
    public void IsEffectivelyEmpty(string[]? lst, bool expected) =>
        Assert.Equal(expected, ScanStrategy.IsEffectivelyEmpty(lst));

    [Fact]
    public void HasNoCarHints_True_WhenNullOrNoCar()
    {
        Assert.True(ScanStrategy.HasNoLetterHints(null));
        Assert.True(ScanStrategy.HasNoLetterHints(new[] { new Hint(1, null) }));
        Assert.True(ScanStrategy.HasNoLetterHints(new[] { new Hint(1, "") }));
    }

    [Fact]
    public void HasNoCarHints_False_WhenHasCar() =>
        Assert.False(ScanStrategy.HasNoLetterHints(new[] { new Hint(1, "a") }));

    // ---------------------------------------------------------------------------
    // MatchesContent
    // ---------------------------------------------------------------------------

    [Fact]
    public void MatchesContent_NonStrict_AllLettersInPool()
    {
        var set = new LetterSet(["a", "i", "l", "e", "s"]);
        var freq = WordBase.BuildFreq("ailes");
        Assert.True(ScanStrategy.MatchesContent("ailes", set, null, false, freq));
    }

    [Fact]
    public void MatchesContent_NonStrict_MissingLetter()
    {
        var set = new LetterSet(["a", "i", "l"]);
        var freq = WordBase.BuildFreq("ailes");
        Assert.False(ScanStrategy.MatchesContent("ailes", set, null, false, freq));
    }

    [Fact]
    public void MatchesContent_Strict_FrequencyOk()
    {
        // pool has 2×a, 1×i, 1×l, 1×e, 1×s — word "ailes" uses each once
        var avail = new List<string> { "a", "a", "i", "l", "e", "s" };
        var (set, poolFreq) = ScanStrategy.BuildAvailStructures(avail, true);
        var wordFreq = WordBase.BuildFreq("ailes");
        Assert.True(ScanStrategy.MatchesContent("ailes", set, poolFreq, true, wordFreq));
    }

    [Fact]
    public void MatchesContent_Strict_FrequencyExceeded()
    {
        // pool has only 1×a but "abba" needs 2×a
        var avail = new List<string> { "a", "b" };
        var (set, poolFreq) = ScanStrategy.BuildAvailStructures(avail, true);
        var wordFreq = WordBase.BuildFreq("abba");
        Assert.False(ScanStrategy.MatchesContent("abba", set, poolFreq, true, wordFreq));
    }

    [Fact]
    public void MatchesContent_AccentNormalized()
    {
        // "élan" normalizes to "elan"; pool contains e,l,a,n
        var set = new LetterSet(["e", "l", "a", "n"]);
        var normalized = WordBase.Normalize("élan");
        var freq = WordBase.BuildFreq(normalized);
        Assert.True(ScanStrategy.MatchesContent(normalized, set, null, false, freq));
    }

    // ---------------------------------------------------------------------------
    // MatchesHints
    // ---------------------------------------------------------------------------

    [Fact]
    public void MatchesHints_NoHints_True() =>
        Assert.True(ScanStrategy.MatchesHints("hello", null));

    [Fact]
    public void MatchesHints_PinnedMatch()
    {
        var hints = new[] { new Hint(1, "h") };
        Assert.True(ScanStrategy.MatchesHints("hello", hints));
    }

    [Fact]
    public void MatchesHints_PinnedMismatch()
    {
        var hints = new[] { new Hint(1, "x") };
        Assert.False(ScanStrategy.MatchesHints("hello", hints));
    }

    [Fact]
    public void MatchesHints_Excluded_Match_ReturnsFalse()
    {
        // excluded hint: word must NOT have 'h' at pos 1, but it does
        var hints = new[] { new Hint(1, "h", Excluded: true) };
        Assert.False(ScanStrategy.MatchesHints("hello", hints));
    }

    [Fact]
    public void MatchesHints_Excluded_NoMatch_ReturnsTrue()
    {
        var hints = new[] { new Hint(1, "x", Excluded: true) };
        Assert.True(ScanStrategy.MatchesHints("hello", hints));
    }

    [Fact]
    public void MatchesHints_PositionOutOfRange_PinnedReturnsFalse()
    {
        var hints = new[] { new Hint(10, "h") };
        Assert.False(ScanStrategy.MatchesHints("hello", hints));
    }

    [Fact]
    public void MatchesHints_PositionOutOfRange_ExcludedReturnsTrue()
    {
        var hints = new[] { new Hint(10, "h", Excluded: true) };
        Assert.True(ScanStrategy.MatchesHints("hello", hints));
    }

    // ---------------------------------------------------------------------------
    // Integration: SearchInFile
    // ---------------------------------------------------------------------------

    [Fact]
    public void SearchInFile_ByContent_Strict()
    {
        var svc = new SearchDispatcher();
        var result = svc.FileDispatch("fr", 5, new[] { "e", "l", "i", "s", "a" }, null, strict: true);
        Assert.Equal(8, result.Count);
        Assert.Contains("ailes", result);
    }

    [Fact]
    public void SearchInFile_ByHint_Pinned()
    {
        var svc = new SearchDispatcher();
        var hints = new[] { new Hint(1, "s"), new Hint(3, "a"), new Hint(5, "e") };
        var result = svc.FileDispatch("fr", 5, null, hints, strict: false);
        Assert.Equal(8, result.Count);
        Assert.Contains("slave", result);
    }

    [Fact]
    public void SearchInFile_ContentAndHint()
    {
        var svc = new SearchDispatcher();
        var hints = new[] { new Hint(1, "l"), new Hint(5, "s") };
        var result = svc.FileDispatch("fr", 5, new[] { "e", "l", "i", "s", "a" }, hints, strict: false);
        Assert.Equal(11, result.Count);
    }

    // ---------------------------------------------------------------------------
    // Integration: SearchInMany
    // ---------------------------------------------------------------------------

    [Fact]
    public void SearchInMany_Guillaume()
    {
        var svc = new SearchDispatcher();
        var result = svc.ManyBaseline("fr", "guillaume", null);
        Assert.Equal(494, result.Count);
    }

    [Fact]
    public void SearchInMany_WithHint()
    {
        var svc = new SearchDispatcher();
        var hints = new[] { new Hint(4, "a") };
        var result = svc.ManyBaseline("fr", "guillaume", hints);
        Assert.True(result.Count > 0);
        Assert.All(result, w => Assert.Equal('a', w.Length >= 4 ? w[3] : ' '));
    }

    // ---------------------------------------------------------------------------
    // Strategy equivalence: Indexed == Scan
    // ---------------------------------------------------------------------------

    [Fact]
    public void IndexedEqualsScaneForContentOnlyQuery()
    {
        var letters = new[] { "e", "l", "i", "s", "a" };
        var scan = SearchDispatcher.Scan.SearchInFile("fr", 5, letters, null, false);
        var indexed = SearchDispatcher.Indexed.SearchInFile("fr", 5, letters, null, false);
        Assert.Equal(scan, indexed);
    }

    [Fact]
    public void IndexedEqualsScaneForHintOnlyQuery()
    {
        var hints = new[] { new Hint(1, "s"), new Hint(3, "a") };
        var scan = SearchDispatcher.Scan.SearchInFile("fr", 5, null, hints, false);
        var indexed = SearchDispatcher.Indexed.SearchInFile("fr", 5, null, hints, false);
        Assert.Equal(scan, indexed);
    }

    [Fact]
    public void IndexedEqualsScaneForMixedQuery()
    {
        var letters = new[] { "e", "l", "i", "s", "a" };
        var hints = new[] { new Hint(1, "l") };
        var scan = SearchDispatcher.Scan.SearchInFile("fr", 5, letters, hints, false);
        var indexed = SearchDispatcher.Indexed.SearchInFile("fr", 5, letters, hints, false);
        Assert.Equal(scan, indexed);
    }

    // ---------------------------------------------------------------------------
    // Input guards
    // ---------------------------------------------------------------------------

    [Theory]
    [InlineData("../../etc")]
    [InlineData("/etc")]
    [InlineData("fr/../en")]
    [InlineData("")]
    public void UnsafeLangIsRejected(string lang)
    {
        Assert.False(WordBase.IsValidLang(lang));
        Assert.Throws<ArgumentException>(() => WordBase.Load(lang, 5));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    public void HintPositionBelowOneIsOutOfRange(int position)
    {
        Assert.False(ScanStrategy.MatchesHints("abc", new[] { new Hint(position, "a") }));
        Assert.True(ScanStrategy.MatchesHints("abc", new[] { new Hint(position, "a", Excluded: true) }));
    }
}
