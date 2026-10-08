namespace WordSearch.Api.Search;

/// <summary>
/// A query's available letters as a membership table, built once per search, so the
/// per-character check in the scan allocates nothing. Each element of the pool is one
/// character; an element of several characters can never match a single letter.
/// </summary>
public sealed class LetterSet
{
    private readonly bool[] _ascii = new bool[128];
    private readonly HashSet<char> _other = [];

    public LetterSet(IEnumerable<string> letters)
    {
        foreach (var l in letters)
        {
            if (l is not { Length: 1 }) continue;
            var c = l[0];
            if (c < 128) _ascii[c] = true;
            else _other.Add(c);
        }
    }

    public bool Contains(char c) => c < 128 ? _ascii[c] : _other.Contains(c);
}
