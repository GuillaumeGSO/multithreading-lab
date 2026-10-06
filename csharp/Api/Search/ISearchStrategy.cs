
namespace WordSearch.Api.Search;

public interface ISearchStrategy
{
    string Name { get; }
    IReadOnlyList<string> SearchInFile(
        string lang, int wordLength,
        IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints,
        bool strict);
}
