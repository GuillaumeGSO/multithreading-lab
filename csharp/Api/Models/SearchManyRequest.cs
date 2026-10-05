namespace WordSearch.Api.Models;

public record SearchManyRequest(
    string Lang = "fr",
    string Cars = "",
    IReadOnlyList<Hint>? LstHint = null);
