namespace WordSearch.Api.Models;

/// <summary>Positional constraint on a word.</summary>
/// <param name="Pos">1-indexed position of the constraint in the word.</param>
/// <param name="Car">Expected character at <paramref name="Pos"/>; null means no character constraint.</param>
/// <param name="Inverted">When true, the character must NOT appear at <paramref name="Pos"/>.</param>
public record Hint(int Pos, string? Car, bool Inverted = false);
