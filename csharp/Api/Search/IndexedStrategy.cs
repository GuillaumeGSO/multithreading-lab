using System.Collections.Concurrent;
using WordSearch.Api.Models;

namespace WordSearch.Api.Search;

public sealed class IndexedStrategy : ISearchStrategy
{
    public string Name => "indexed";

    private static readonly ConcurrentDictionary<
        string,
        IReadOnlyDictionary<int, IReadOnlyDictionary<char, IReadOnlySet<string>>>> IndexCache = new();

    public IReadOnlyList<string> SearchInFile(
        string lang, int nbCar,
        IReadOnlyList<string>? lstCar,
        IReadOnlyList<Hint>? lstHint,
        bool strict)
    {
        ScanStrategy.ValidateParams(lstCar, lstHint);
        var entries = WordBase.Load(lang, nbCar);
        var posIdx = EnsureIndex(lang, nbCar, entries);

        bool emptyCars = ScanStrategy.IsEffectivelyEmpty(lstCar);
        bool emptyHints = ScanStrategy.HasNoCarHints(lstHint);

        IReadOnlySet<string>? candidates = null;
        if (!emptyHints)
        {
            var activeHints = (lstHint ?? []).Where(h => !string.IsNullOrEmpty(h.Car)).ToList();

            foreach (var hint in activeHints)
            {
                if (hint.Inverted) continue;
                int pos = hint.Pos;
                if (pos > nbCar) return Array.Empty<string>();
                var set = posIdx.TryGetValue(pos, out var cm) && cm.TryGetValue(hint.Car![0], out var ws)
                    ? ws : (IReadOnlySet<string>)new HashSet<string>();
                candidates = candidates == null ? set : (IReadOnlySet<string>)candidates.Intersect(set).ToHashSet();
            }

            // If no pinned hints seeded candidates, use all words
            if (candidates == null)
                candidates = entries.Select(e => e.Word).ToHashSet();

            foreach (var hint in activeHints)
            {
                if (!hint.Inverted) continue;
                int pos = hint.Pos;
                if (pos > nbCar) continue;
                if (posIdx.TryGetValue(pos, out var cm) && cm.TryGetValue(hint.Car![0], out var excluded))
                    candidates = (IReadOnlySet<string>)candidates.Except(excluded).ToHashSet();
            }
        }

        var avail = ScanStrategy.BuildAvail(lstCar);
        var (availSet, availFreq) = ScanStrategy.BuildAvailStructures(avail, strict);

        // Yield in original word-list order
        var results = new List<string>();
        foreach (var entry in entries)
        {
            if (candidates != null && !candidates.Contains(entry.Word)) continue;
            if (!emptyCars && !ScanStrategy.MatchesContent(entry.Normalized, availSet, availFreq, strict, entry.Freq))
                continue;
            results.Add(entry.Word);
        }
        return results;
    }

    private static IReadOnlyDictionary<int, IReadOnlyDictionary<char, IReadOnlySet<string>>>
        EnsureIndex(string lang, int nbCar, IReadOnlyList<WordEntry> entries)
    {
        return IndexCache.GetOrAdd($"{lang}/{nbCar}", _ => BuildIndex(entries));
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
