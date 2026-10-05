namespace WordSearch.Api.Models;

public record SearchFileRequest(
    string Lang = "fr",
    int NbCar = 0,
    IReadOnlyList<string>? LstCar = null,
    IReadOnlyList<Hint>? LstHint = null,
    bool Strict = false);
