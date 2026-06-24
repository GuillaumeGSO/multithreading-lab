package com.lab.search.service.strategy;

import com.lab.search.model.Hint;
import com.lab.search.service.WordSearchService;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Positional inverted index strategy. Builds a pos→char→Set(word) index per
 * (lang/nbCar) key. For queries with at least one pinned hint, intersecting the
 * index buckets yields a tiny candidate set — O(result) instead of O(vocabulary).
 *
 * Chosen by the dispatcher when hasPinned(lstHint) is true.
 * Falls back to matchesHints for the rare direct-call edge case (excluded-only hints).
 */
public final class IndexedStrategy implements SearchStrategy {

    // key = "lang/nbCar" → pos (1-based) → raw char → immutable set of words
    private final ConcurrentHashMap<String, Map<Integer, Map<String, Set<String>>>> indexCache
            = new ConcurrentHashMap<>();

    @Override
    public String name() { return "indexed"; }

    private Map<Integer, Map<String, Set<String>>> ensureIndex(String lang, int nbCar, List<String> words) {
        return indexCache.computeIfAbsent(lang + "/" + nbCar, k -> buildIndex(words));
    }

    private static Map<Integer, Map<String, Set<String>>> buildIndex(List<String> words) {
        Map<Integer, Map<String, Set<String>>> idx = new HashMap<>();
        for (String word : words) {
            for (int pos = 1; pos <= word.length(); pos++) {
                String ch = String.valueOf(word.charAt(pos - 1));
                idx.computeIfAbsent(pos, k -> new HashMap<>())
                   .computeIfAbsent(ch, k -> new HashSet<>())
                   .add(word);
            }
        }
        // Freeze inner maps and sets so concurrent reads need no locking
        Map<Integer, Map<String, Set<String>>> frozen = new LinkedHashMap<>(idx.size());
        idx.forEach((pos, charMap) -> {
            Map<String, Set<String>> frozenCharMap = new LinkedHashMap<>(charMap.size());
            charMap.forEach((ch, wordSet) ->
                    frozenCharMap.put(ch, Collections.unmodifiableSet(wordSet)));
            frozen.put(pos, Collections.unmodifiableMap(frozenCharMap));
        });
        return Collections.unmodifiableMap(frozen);
    }

    @Override
    public List<String> searchInFile(String lang, int nbCar, List<String> words,
                                     List<String> lstCar, List<Hint> lstHint,
                                     boolean strict, boolean emptyCars, boolean emptyHints) {
        Set<String> candidates = null; // null = "all words"

        if (!emptyHints) {
            // Only build the index when at least one pinned hint exists to seed candidates.
            // Excluded-only or hint-free queries fall through to the matchesHints fallback below.
            boolean anyPinned = false;
            for (Hint h : lstHint)
                if (h.car() != null && !h.car().isEmpty() && !h.inverted()) { anyPinned = true; break; }

            if (anyPinned) {
                var posIdx = ensureIndex(lang, nbCar, words);

                // Step 1: intersect pinned hints to seed a tight candidate set
                for (Hint hint : lstHint) {
                    if (hint.car() == null || hint.car().isEmpty() || hint.inverted()) continue;
                    Set<String> bucket = posIdx.getOrDefault(hint.pos(), Map.of())
                                              .getOrDefault(hint.car(), Set.of());
                    candidates = (candidates == null) ? new HashSet<>(bucket)
                                                      : intersect(candidates, bucket);
                }

                // Step 2: subtract excluded hints (only when candidates were seeded)
                if (candidates != null) {
                    for (Hint hint : lstHint) {
                        if (hint.car() == null || hint.car().isEmpty() || !hint.inverted()) continue;
                        candidates.removeAll(posIdx.getOrDefault(hint.pos(), Map.of())
                                                  .getOrDefault(hint.car(), Set.of()));
                    }
                }
            }
        }

        // Step 3: iterate original word-list order for byte-identical output
        List<String> results = new ArrayList<>();
        for (String word : words) {
            if (candidates != null && !candidates.contains(word)) continue;
            if (!emptyCars && !WordSearchService.matchesContent(word, lstCar, strict)) continue;
            // Fallback: excluded-only hints with no pinned hints (e.g. direct fileIndexed call)
            if (candidates == null && !emptyHints && !WordSearchService.matchesHints(word, lstHint)) continue;
            results.add(word);
        }
        return results;
    }

    private static Set<String> intersect(Set<String> a, Set<String> b) {
        Set<String> small = a.size() <= b.size() ? a : b;
        Set<String> large = a.size() <= b.size() ? b : a;
        Set<String> r = new HashSet<>(small.size());
        for (String s : small) if (large.contains(s)) r.add(s);
        return r;
    }
}
