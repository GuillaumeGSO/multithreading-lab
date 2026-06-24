package com.lab.search.service;

import com.lab.search.model.Hint;
import com.lab.search.model.SearchResponse;
import com.lab.search.service.strategy.IndexedStrategy;
import com.lab.search.service.strategy.ScanStrategy;
import com.lab.search.service.strategy.SearchStrategy;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.function.BiFunction;

@Service
public class WordSearchService {

    private final Path assetsRoot;
    private final ConcurrentHashMap<String, List<String>> wordCache = new ConcurrentHashMap<>();
    private final boolean parallel;
    private final int splitDegree;
    private final ScanStrategy    scanStrategy    = new ScanStrategy();
    private final IndexedStrategy indexedStrategy = new IndexedStrategy();

    public WordSearchService() {
        this(Path.of(envOr("ASSETS_ROOT", "assets")));
    }

    WordSearchService(Path assetsRoot) {
        this.assetsRoot = assetsRoot;
        // SEARCH_MODE=parallel (default) routes the API through the threaded
        // variants; SEARCH_MODE=baseline restores the original per-length
        // fan-out behavior. The benchmark calls the modes explicitly regardless.
        this.parallel = !"baseline".equalsIgnoreCase(System.getenv("SEARCH_MODE"));
        this.splitDegree = parseSplitDegree();
    }

    private static String envOr(String key, String def) {
        var v = System.getenv(key);
        return v != null && !v.isEmpty() ? v : def;
    }

    /// Chunks per file (axis B). `SPLIT_DEGREE` env, default 2 ("halves").
    private static int parseSplitDegree() {
        try {
            int n = Integer.parseInt(envOr("SPLIT_DEGREE", "2"));
            return Math.max(1, n);
        } catch (NumberFormatException e) {
            return 2;
        }
    }

    public int splitDegree() {
        return splitDegree;
    }

    // --- API entry points (controller) ---

    public SearchResponse searchInFile(String lang, int nbCar, List<String> lstCar, List<Hint> lstHint, boolean strict) {
        var words = parallel
                ? fileSplit(lang, nbCar, lstCar, lstHint, strict, splitDegree)
                : fileDispatch(lang, nbCar, lstCar, lstHint, strict);
        return SearchResponse.of(words);
    }

    public SearchResponse searchInManyFiles(String lang, String cars, List<Hint> lstHint) {
        var words = parallel
                ? manyNested(lang, cars, lstHint, splitDegree)
                : manyFanout(lang, cars, lstHint);
        return SearchResponse.of(words);
    }

    // --- strategy dispatch (baseline path for /search/file) ---

    /// Routes to IndexedStrategy when a pinned hint is present, ScanStrategy otherwise.
    /// Used by searchInFile() when parallel=false; also callable directly (tests, benchmark).
    public List<String> fileDispatch(String lang, int nbCar, List<String> lstCar, List<Hint> lstHint, boolean strict) {
        if (isEffectivelyEmpty(lstCar) && hasNoCarHints(lstHint)) {
            throw new IllegalArgumentException("Either lst_car or lst_hint must be provided");
        }
        var words = loadWords(lang, nbCar);
        return chooseStrategy(lstHint).searchInFile(lang, nbCar, words, lstCar, lstHint, strict,
                isEffectivelyEmpty(lstCar), hasNoCarHints(lstHint));
    }

    /// Forces IndexedStrategy regardless of hints. Used for benchmarking and direct tests.
    public List<String> fileIndexed(String lang, int nbCar, List<String> lstCar, List<Hint> lstHint, boolean strict) {
        if (isEffectivelyEmpty(lstCar) && hasNoCarHints(lstHint)) {
            throw new IllegalArgumentException("Either lst_car or lst_hint must be provided");
        }
        var words = loadWords(lang, nbCar);
        return indexedStrategy.searchInFile(lang, nbCar, words, lstCar, lstHint, strict,
                isEffectivelyEmpty(lstCar), hasNoCarHints(lstHint));
    }

    private SearchStrategy chooseStrategy(List<Hint> lstHint) {
        return hasPinned(lstHint) ? indexedStrategy : scanStrategy;
    }

    private static boolean hasPinned(List<Hint> lstHint) {
        if (lstHint == null) return false;
        for (Hint h : lstHint)
            if (h.car() != null && !h.car().isEmpty() && !h.inverted()) return true;
        return false;
    }

    // --- search modes (also called directly by the benchmark) ---

    /// scan filters words[from, to) by the letter pool and/or hints, in order.
    /// Single per-word predicate shared by sequential and parallel paths, so
    /// they always agree on matches and ordering. Thread-safe over a shared
    /// lstCar (matchesContent copies internally for strict mode).
    private List<String> scan(List<String> words, int from, int to, List<String> lstCar,
                              List<Hint> lstHint, boolean strict, boolean emptyCars, boolean emptyHints) {
        List<String> results = new ArrayList<>();
        for (int i = from; i < to; i++) {
            String word = words.get(i);
            boolean contentOk = emptyCars || matchesContent(word, lstCar, strict);
            boolean hintOk = emptyHints || matchesHints(word, lstHint);
            if (contentOk && hintOk) {
                results.add(word);
            }
        }
        return results;
    }

    /// Baseline single-threaded file scan.
    public List<String> fileBaseline(String lang, int nbCar, List<String> lstCar, List<Hint> lstHint, boolean strict) {
        if (isEffectivelyEmpty(lstCar) && hasNoCarHints(lstHint)) {
            throw new IllegalArgumentException("Either lst_car or lst_hint must be provided");
        }
        var words = loadWords(lang, nbCar);
        return scan(words, 0, words.size(), lstCar, lstHint, strict,
                isEffectivelyEmpty(lstCar), hasNoCarHints(lstHint));
    }

    /// Intra-file split (axis B): word list scanned in `threads` contiguous
    /// chunks on virtual threads, merged in index order (== fileBaseline).
    public List<String> fileSplit(String lang, int nbCar, List<String> lstCar, List<Hint> lstHint, boolean strict, int threads) {
        if (isEffectivelyEmpty(lstCar) && hasNoCarHints(lstHint)) {
            throw new IllegalArgumentException("Either lst_car or lst_hint must be provided");
        }
        var words = loadWords(lang, nbCar);
        boolean emptyCars = isEffectivelyEmpty(lstCar);
        boolean emptyHints = hasNoCarHints(lstHint);
        int n = Math.max(1, Math.min(threads, Math.max(1, words.size())));
        if (n <= 1) {
            return scan(words, 0, words.size(), lstCar, lstHint, strict, emptyCars, emptyHints);
        }
        int chunk = (words.size() + n - 1) / n; // ceil keeps chunks contiguous
        var futures = new ArrayList<Future<List<String>>>();
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int idx = 0; idx < n; idx++) {
                final int start = Math.min(idx * chunk, words.size());
                final int end = Math.min(start + chunk, words.size());
                futures.add(executor.submit(() ->
                        scan(words, start, end, lstCar, lstHint, strict, emptyCars, emptyHints)));
            }
        }
        return drain(futures, false);
    }

    /// Baseline sequential scan across every length (no concurrency).
    public List<String> manyBaseline(String lang, String cars, List<Hint> lstHint) {
        validateCars(cars);
        int minLen = minLength(lstHint);
        int maxLen = cars.length();
        List<String> results = new ArrayList<>();
        for (int len = maxLen; len >= minLen; len--) {
            try {
                List<String> lstCar = new ArrayList<>(List.of(cars.split("")));
                results.addAll(fileBaseline(lang, len, lstCar, lstHint, false));
            } catch (UncheckedIOException e) {
                // skip lengths with no word file
            }
        }
        return results;
    }

    /// Per-length fan-out (axis A) over virtual threads. (Original Java model.)
    public List<String> manyFanout(String lang, String cars, List<Hint> lstHint) {
        return manyParallel(cars, lstHint, (len, lstCar) -> fileBaseline(lang, len, lstCar, lstHint, false));
    }

    /// Nested: per-length fan-out (axis A) AND each length split into `threads`
    /// chunks (axis B) — virtual threads spawning virtual threads. Output is
    /// identical to manyFanout.
    public List<String> manyNested(String lang, String cars, List<Hint> lstHint, int threads) {
        return manyParallel(cars, lstHint, (len, lstCar) -> fileSplit(lang, len, lstCar, lstHint, false, threads));
    }

    private List<String> manyParallel(String cars, List<Hint> lstHint,
                                      BiFunction<Integer, List<String>, List<String>> scanLen) {
        validateCars(cars);
        int minLen = minLength(lstHint);
        int maxLen = cars.length();
        var futures = new ArrayList<Future<List<String>>>();
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int len = maxLen; len >= minLen; len--) {
                final int nbCar = len;
                futures.add(executor.submit(() -> {
                    List<String> lstCar = new ArrayList<>(List.of(cars.split("")));
                    return scanLen.apply(nbCar, lstCar);
                }));
            }
        }
        // skipFailures=true: a length with no word file surfaces as an
        // ExecutionException and is skipped (matches manyBaseline's catch).
        return drain(futures, true);
    }

    /// Merges chunk/length futures in submit order (preserving the baseline
    /// ordering). `skipFailures` mirrors manyParallel's tolerance of missing
    /// word files: when true an ExecutionException is swallowed, otherwise its
    /// cause is rethrown.
    private static List<String> drain(List<Future<List<String>>> futures, boolean skipFailures) {
        List<String> results = new ArrayList<>();
        for (var f : futures) {
            try {
                results.addAll(f.get());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException(e);
            } catch (ExecutionException e) {
                if (!skipFailures) {
                    throw new RuntimeException(e.getCause());
                }
            }
        }
        return results;
    }

    private static void validateCars(String cars) {
        if (cars == null || cars.isEmpty()) {
            throw new IllegalArgumentException("cars must be provided");
        }
    }

    /// A normal (non-inverted) hint at position N forces words of length >= N.
    private static int minLength(List<Hint> lstHint) {
        return lstHint.stream()
                .filter(h -> h.car() != null && !h.inverted())
                .mapToInt(Hint::pos)
                .max()
                .orElse(1);
    }

    // --- helpers ---

    private List<String> loadWords(String lang, int nbCar) {
        var key = lang + "/" + nbCar;
        return wordCache.computeIfAbsent(key, k -> {
            var file = assetsRoot.resolve(lang).resolve(nbCar + ".txt");
            try {
                return Files.readAllLines(file);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        });
    }

    /// Normalize accents: "éàü" → "eau" (NFD + strip combining marks).
    private static String normalize(String s) {
        return Normalizer.normalize(s, Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}", "");
    }

    public static boolean matchesContent(String word, List<String> lstCar, boolean strict) {
        String normalized = normalize(word);
        if (normalized.isEmpty() || lstCar.isEmpty()) return false;
        if (strict) {
            // Each letter must be consumed exactly once — work on a mutable copy
            List<String> available = new ArrayList<>(lstCar);
            for (char c : normalized.toCharArray()) {
                String ch = String.valueOf(c);
                int idx = available.indexOf(ch);
                if (idx == -1) return false;
                available.remove(idx);
            }
            return true;
        } else {
            for (char c : normalized.toCharArray()) {
                if (!lstCar.contains(String.valueOf(c))) return false;
            }
            return true;
        }
    }

    public static boolean matchesHints(String word, List<Hint> lstHint) {
        for (Hint hint : lstHint) {
            if (hint.car() == null) continue;
            int pos = hint.pos();
            if (!hint.inverted() && pos > word.length()) return false;
            if (pos > word.length()) continue;
            char actual = word.charAt(pos - 1);
            char expected = hint.car().charAt(0);
            if (hint.inverted()) {
                if (actual == expected) return false;
            } else {
                if (actual != expected) return false;
            }
        }
        return true;
    }

    public static boolean isEffectivelyEmpty(List<String> lst) {
        return lst == null || lst.stream().allMatch(s -> s == null || s.isEmpty());
    }

    public static boolean hasNoCarHints(List<Hint> lst) {
        return lst == null || lst.stream().allMatch(h -> h.car() == null || h.car().isEmpty());
    }
}
