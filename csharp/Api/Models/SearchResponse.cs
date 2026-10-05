namespace WordSearch.Api.Models;

public record SearchResponse(IReadOnlyList<string> Words, int Count)
{
    public static SearchResponse Of(IReadOnlyList<string> words) => new(words, words.Count);
}
