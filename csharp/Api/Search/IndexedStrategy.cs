using System.Collections.Concurrent;

namespace WordSearch.Api.Search;

public sealed class IndexedStrategy : ISearchStrategy
{
    public string Name => "indexed";

    private static readonly ConcurrentDictionary<
        string,
        IReadOnlyDictionary<int, IReadOnlyDictionary<char, IReadOnlySet<string>>>> IndexCache = new();

    public IReadOnlyList<string> SearchInFile(
        string lang, int wordLength,
        IReadOnlyList<string>? letters,
        IReadOnlyList<Hint>? hints,
        bool strict)
    {
        ScanStrategy.ValidateParams(wordLength, letters, hints);
        var entries = WordBase.Load(lang, wordLength);
        var posIdx = EnsureIndex(lang, wordLength, entries);

        bool emptyLetters = ScanStrategy.IsEffectivelyEmpty(letters);
        bool emptyHints = ScanStrategy.HasNoLetterHints(hints);

        IReadOnlySet<string>? candidates = null;
        if (!emptyHints)
        {
            var activeHints = (hints ?? []).Where(h => !string.IsNullOrEmpty(h.Letter)).ToList();

            foreach (var hint in activeHints)
            {
                if (hint.Excluded) continue;
                int pos = hint.Position;
                if (pos > wordLength) return Array.Empty<string>();
                var set = posIdx.TryGetValue(pos, out var cm) && cm.TryGetValue(hint.Letter![0], out var ws)
                    ? ws : (IReadOnlySet<string>)new HashSet<string>();
                candidates = candidates == null ? set : (IReadOnlySet<string>)candidates.Intersect(set).ToHashSet();
            }

            // If no pinned hints seeded candidates, use all words
            if (candidates == null)
                candidates = entries.Select(e => e.Word).ToHashSet();

            foreach (var hint in activeHints)
            {
                if (!hint.Excluded) continue;
                int pos = hint.Position;
                if (pos > wordLength) continue;
                if (posIdx.TryGetValue(pos, out var cm) && cm.TryGetValue(hint.Letter![0], out var excluded))
                    candidates = (IReadOnlySet<string>)candidates.Except(excluded).ToHashSet();
            }
        }

        var avail = ScanStrategy.BuildAvail(letters);
        var (availSet, availFreq) = ScanStrategy.BuildAvailStructures(avail, strict);

        // Yield in original word-list order
        var results = new List<string>();
        foreach (var entry in entries)
        {
            if (candidates != null && !candidates.Contains(entry.Word)) continue;
            if (!emptyLetters && !ScanStrategy.MatchesContent(entry.Normalized, availSet, availFreq, strict, entry.Freq))
                continue;
            results.Add(entry.Word);
        }
        return results;
    }

    private static IReadOnlyDictionary<int, IReadOnlyDictionary<char, IReadOnlySet<string>>>
        EnsureIndex(string lang, int wordLength, IReadOnlyList<WordEntry> entries)
    {
        return IndexCache.GetOrAdd($"{lang}/{wordLength}", _ => BuildIndex(entries));
    }

    private static IReadOnlyDictionary<int, IReadOnlyDictionary<char, IReadOnlySet<string>>>
        BuildIndex(IReadOnlyList<WordEntry> entries)
    {
        var idx = new Dictionary<int, Dictionary<char, HashSet<string>>>();
        foreach (var entry in entries)
        {
            for (int pos = 1; pos <= entry.Word.Length; pos++)
            {
                char c = entry.Word[pos - 1];
                if (!idx.TryGetValue(pos, out var cm))
                    idx[pos] = cm = new Dictionary<char, HashSet<string>>();
                if (!cm.TryGetValue(c, out var ws))
                    cm[c] = ws = new HashSet<string>();
                ws.Add(entry.Word);
            }
        }
        return idx.ToDictionary(
            kv => kv.Key,
            kv => (IReadOnlyDictionary<char, IReadOnlySet<string>>)kv.Value.ToDictionary(
                ckv => ckv.Key,
                ckv => (IReadOnlySet<string>)ckv.Value));
    }
}
