namespace WordSearch.Api.Models;

/// <summary>Word search result.</summary>
/// <param name="Words">Matching words in scan order (longest-first for /search/many).</param>
/// <param name="Count">Total number of matching words — equals Words.Count.</param>
public record SearchResponse(IReadOnlyList<string> Words, int Count)
{
    public static SearchResponse Of(IReadOnlyList<string> words) => new(words, words.Count);
}
