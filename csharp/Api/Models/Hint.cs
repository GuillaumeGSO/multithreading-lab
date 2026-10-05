namespace WordSearch.Api.Models;

public record Hint(int Pos, string? Car, bool Inverted = false);
