package com.lab.search.service;

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

    public List<String> searchInFile(String lang, int wordLength, List<String> letters, List<Hint> hints, boolean strict) {
        return parallel
                ? fileSplit(lang, wordLength, letters, hints, strict, splitDegree)
                : fileDispatch(lang, wordLength, letters, hints, strict);
    }

    public List<String> searchInManyFiles(String lang, String letters, List<Hint> hints) {
        return parallel
                ? manyNested(lang, letters, hints, splitDegree)
                : manyFanout(lang, letters, hints);
    }

    // --- strategy dispatch (baseline path for /search/file) ---

    /// Routes to IndexedStrategy when a pinned hint is present, ScanStrategy otherwise.
    /// Used by searchInFile() when parallel=false; also callable directly (tests, benchmark).
    public List<String> fileDispatch(String lang, int wordLength, List<String> letters, List<Hint> hints, boolean strict) {
        if (wordLength <= 0 || (isEffectivelyEmpty(letters) && hasNoLetterHints(hints))) {
            throw new IllegalArgumentException("letters and hints cannot both be empty");
        }
        var words = loadWords(lang, wordLength);
        return chooseStrategy(hints).searchInFile(lang, wordLength, words, letters, hints, strict,
                isEffectivelyEmpty(letters), hasNoLetterHints(hints));
    }

    /// Forces IndexedStrategy regardless of hints. Used for benchmarking and direct tests.
    public List<String> fileIndexed(String lang, int wordLength, List<String> letters, List<Hint> hints, boolean strict) {
        if (wordLength <= 0 || (isEffectivelyEmpty(letters) && hasNoLetterHints(hints))) {
            throw new IllegalArgumentException("letters and hints cannot both be empty");
        }
        var words = loadWords(lang, wordLength);
        return indexedStrategy.searchInFile(lang, wordLength, words, letters, hints, strict,
                isEffectivelyEmpty(letters), hasNoLetterHints(hints));
    }

    private SearchStrategy chooseStrategy(List<Hint> hints) {
        return hasPinned(hints) ? indexedStrategy : scanStrategy;
    }

    private static boolean hasPinned(List<Hint> hints) {
        if (hints == null) return false;
        for (Hint h : hints)
            if (h.letter() != null && !h.letter().isEmpty() && !h.excluded()) return true;
        return false;
    }

    // --- search modes (also called directly by the benchmark) ---

    /// scan filters words[from, to) by the letter pool and/or hints, in order.
    /// Single per-word predicate shared by sequential and parallel paths, so
    /// they always agree on matches and ordering. Thread-safe over a shared
    /// letters (matchesContent copies internally for strict mode).
    private List<String> scan(List<String> words, int from, int to, List<String> letters,
                              List<Hint> hints, boolean strict, boolean emptyLetters, boolean emptyHints) {
        List<String> results = new ArrayList<>();
        for (int i = from; i < to; i++) {
            String word = words.get(i);
            boolean contentOk = emptyLetters || matchesContent(word, letters, strict);
            boolean hintOk = emptyHints || matchesHints(word, hints);
            if (contentOk && hintOk) {
                results.add(word);
            }
        }
        return results;
    }

    /// Baseline single-threaded file scan.
    public List<String> fileBaseline(String lang, int wordLength, List<String> letters, List<Hint> hints, boolean strict) {
        if (wordLength <= 0 || (isEffectivelyEmpty(letters) && hasNoLetterHints(hints))) {
            throw new IllegalArgumentException("letters and hints cannot both be empty");
        }
        var words = loadWords(lang, wordLength);
        return scan(words, 0, words.size(), letters, hints, strict,
                isEffectivelyEmpty(letters), hasNoLetterHints(hints));
    }

    /// Intra-file split (axis B): word list scanned in `threads` contiguous
    /// chunks on virtual threads, merged in index order (== fileBaseline).
    public List<String> fileSplit(String lang, int wordLength, List<String> letters, List<Hint> hints, boolean strict, int threads) {
        if (wordLength <= 0 || (isEffectivelyEmpty(letters) && hasNoLetterHints(hints))) {
            throw new IllegalArgumentException("letters and hints cannot both be empty");
        }
        var words = loadWords(lang, wordLength);
        boolean emptyLetters = isEffectivelyEmpty(letters);
        boolean emptyHints = hasNoLetterHints(hints);
        int n = Math.max(1, Math.min(threads, Math.max(1, words.size())));
        if (n <= 1) {
            return scan(words, 0, words.size(), letters, hints, strict, emptyLetters, emptyHints);
        }
        int chunk = (words.size() + n - 1) / n; // ceil keeps chunks contiguous
        var futures = new ArrayList<Future<List<String>>>();
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int idx = 0; idx < n; idx++) {
                final int start = Math.min(idx * chunk, words.size());
                final int end = Math.min(start + chunk, words.size());
                futures.add(executor.submit(() ->
                        scan(words, start, end, letters, hints, strict, emptyLetters, emptyHints)));
            }
        }
        return drain(futures, false);
    }

    /// Baseline sequential scan across every length (no concurrency).
    public List<String> manyBaseline(String lang, String letters, List<Hint> hints) {
        validateLetters(letters);
        int minLen = minLength(hints);
        int maxLen = letters.length();
        List<String> results = new ArrayList<>();
        for (int len = maxLen; len >= minLen; len--) {
            try {
                List<String> pool = new ArrayList<>(List.of(letters.split("")));
                results.addAll(fileBaseline(lang, len, pool, hints, false));
            } catch (UncheckedIOException e) {
                // skip lengths with no word file
            }
        }
        return results;
    }

    /// Per-length fan-out (axis A) over virtual threads. (Original Java model.)
    public List<String> manyFanout(String lang, String letters, List<Hint> hints) {
        return manyParallel(letters, hints, (len, pool) -> fileBaseline(lang, len, pool, hints, false));
    }

    /// Nested: per-length fan-out (axis A) AND each length split into `threads`
    /// chunks (axis B) — virtual threads spawning virtual threads. Output is
    /// identical to manyFanout.
    public List<String> manyNested(String lang, String letters, List<Hint> hints, int threads) {
        return manyParallel(letters, hints, (len, pool) -> fileSplit(lang, len, pool, hints, false, threads));
    }

    private List<String> manyParallel(String letters, List<Hint> hints,
                                      BiFunction<Integer, List<String>, List<String>> scanLen) {
        validateLetters(letters);
        int minLen = minLength(hints);
        int maxLen = letters.length();
        var futures = new ArrayList<Future<List<String>>>();
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int len = maxLen; len >= minLen; len--) {
                final int length = len;
                futures.add(executor.submit(() -> {
                    List<String> pool = new ArrayList<>(List.of(letters.split("")));
                    return scanLen.apply(length, pool);
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

    private static void validateLetters(String letters) {
        if (letters == null || letters.isEmpty()) {
            throw new IllegalArgumentException("letters must be provided");
        }
    }

    /// A pinned (non-excluded) hint at position N forces words of length >= N.
    private static int minLength(List<Hint> hints) {
        return hints.stream()
                .filter(h -> h.letter() != null && !h.excluded())
                .mapToInt(Hint::position)
                .max()
                .orElse(1);
    }

    // --- helpers ---

    private List<String> loadWords(String lang, int wordLength) {
        var key = lang + "/" + wordLength;
        return wordCache.computeIfAbsent(key, k -> {
            var file = assetsRoot.resolve(lang).resolve(wordLength + ".txt");
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

    public static boolean matchesContent(String word, List<String> letters, boolean strict) {
        String normalized = normalize(word);
        if (normalized.isEmpty() || letters.isEmpty()) return false;
        if (strict) {
            // Each letter must be consumed exactly once — work on a mutable copy
            List<String> available = new ArrayList<>(letters);
            for (char c : normalized.toCharArray()) {
                String ch = String.valueOf(c);
                int idx = available.indexOf(ch);
                if (idx == -1) return false;
                available.remove(idx);
            }
            return true;
        } else {
            for (char c : normalized.toCharArray()) {
                if (!letters.contains(String.valueOf(c))) return false;
            }
            return true;
        }
    }

    public static boolean matchesHints(String word, List<Hint> hints) {
        for (Hint hint : hints) {
            if (hint.letter() == null) continue;
            int pos = hint.position();
            if (!hint.excluded() && pos > word.length()) return false;
            if (pos > word.length()) continue;
            char actual = word.charAt(pos - 1);
            char expected = hint.letter().charAt(0);
            if (hint.excluded()) {
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

    public static boolean hasNoLetterHints(List<Hint> lst) {
        return lst == null || lst.stream().allMatch(h -> h.letter() == null || h.letter().isEmpty());
    }
}
