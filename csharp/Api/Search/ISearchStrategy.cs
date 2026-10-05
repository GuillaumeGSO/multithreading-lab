using WordSearch.Api.Models;

namespace WordSearch.Api.Search;

public interface ISearchStrategy
{
    string Name { get; }
    IReadOnlyList<string> SearchInFile(
        string lang, int nbCar,
        IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint,
        bool strict);
}
