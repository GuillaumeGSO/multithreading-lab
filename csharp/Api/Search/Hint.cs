namespace WordSearch.Api.Search;

/// <summary>Positional constraint on a word, as used by the search algorithm.</summary>
/// <param name="Position">1-indexed position of the constraint in the word.</param>
/// <param name="Letter">Expected letter at <paramref name="Position"/>; null or empty means no constraint.</param>
/// <param name="Excluded">When true, <paramref name="Letter"/> must NOT appear at <paramref name="Position"/>.</param>
public record Hint(int Position, string? Letter, bool Excluded = false);
