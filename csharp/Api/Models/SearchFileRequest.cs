namespace WordSearch.Api.Models;

/// <summary>Request body for POST /search/file.</summary>
/// <param name="Lang">Language code — selects the dictionary subfolder under assets/.</param>
/// <param name="NbCar">Exact word length to search for.</param>
/// <param name="LstCar">Available letters; empty means no letter-pool constraint.</param>
/// <param name="LstHint">Positional constraints applied after the letter-pool filter.</param>
/// <param name="Strict">When true, each letter may only be used once (Scrabble-style).</param>
public record SearchFileRequest(
    string Lang = "fr",
    int NbCar = 0,
    IReadOnlyList<string>? LstCar = null,
    IReadOnlyList<Hint>? LstHint = null,
    bool Strict = false);
