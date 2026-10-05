namespace WordSearch.Api.Models;

/// <summary>Request body for POST /search/many.</summary>
/// <param name="Lang">Language code — selects the dictionary subfolder under assets/.</param>
/// <param name="Cars">Available letters as a string; max word length equals Cars.Length.</param>
/// <param name="LstHint">Positional constraints applied across every length scanned.</param>
public record SearchManyRequest(
    string Lang = "fr",
    string Cars = "",
    IReadOnlyList<Hint>? LstHint = null);
