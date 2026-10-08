package com.lab.search.service;

import com.lab.search.service.strategy.IndexedStrategy;
import com.lab.search.service.strategy.ScanStrategy;
import com.lab.search.service.strategy.SearchStrategy;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.function.BiFunction;
import java.util.regex.Pattern;

@Service
public class WordSearchService {

    private final Path assetsRoot;
    private final ConcurrentHashMap<String, List<WordEntry>> wordCache = new ConcurrentHashMap<>();
    private final SearchMode mode;
    private final int splitDegree;
    private final ScanStrategy    scanStrategy    = new ScanStrategy();
    private final IndexedStrategy indexedStrategy = new IndexedStrategy();

    public WordSearchService() {
        this(Path.of(envOr("ASSETS_ROOT", "assets")));
    }

    WordSearchService(Path assetsRoot) {
        // SEARCH_MODE picks what the API entry points run (see SearchMode). The
        // benchmark calls each variant explicitly regardless.
        this(assetsRoot, SearchMode.parse(System.getenv("SEARCH_MODE")));
    }

    WordSearchService(Path assetsRoot, SearchMode mode) {
        this.assetsRoot = assetsRoot;
        this.mode = mode;
        this.splitDegree = parseSplitDegree();
    }

    public SearchMode mode() {
        return mode;
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
        return switch (mode) {
            case BASELINE -> fileBaseline(lang, wordLength, letters, hints, strict);
            case PARALLEL -> fileSplit(lang, wordLength, letters, hints, strict, splitDegree);
            case INDEXED -> fileDispatch(lang, wordLength, letters, hints, strict);
        };
    }

    public List<String> searchInManyFiles(String lang, String letters, List<Hint> hints) {
        return switch (mode) {
            case BASELINE, INDEXED -> manyBaseline(lang, letters, hints);
            case PARALLEL -> manyNested(lang, letters, hints, splitDegree);
        };
    }

    // --- strategy dispatch (baseline path for /search/file) ---

    /// Routes to IndexedStrategy when a pinned hint is present, ScanStrategy otherwise.
    /// Used by searchInFile() in the indexed mode; also callable directly (tests, benchmark).
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
    /// they always agree on matches and ordering. The pool is immutable, so one
    /// instance is shared by every chunk. Only the predicates the query needs run.
    static List<String> scan(List<WordEntry> words, int from, int to, LetterPool pool,
                             List<Hint> hints, boolean emptyLetters, boolean emptyHints) {
        List<String> results = new ArrayList<>();
        for (int i = from; i < to; i++) {
            WordEntry e = words.get(i);
            boolean ok = emptyHints ? pool.matches(e)
                    : emptyLetters ? matchesHints(e.word(), hints)
                    : pool.matches(e) && matchesHints(e.word(), hints);
            if (ok) results.add(e.word());
        }
        return results;
    }

    /// Baseline single-threaded file scan.
    public List<String> fileBaseline(String lang, int wordLength, List<String> letters, List<Hint> hints, boolean strict) {
        if (wordLength <= 0 || (isEffectivelyEmpty(letters) && hasNoLetterHints(hints))) {
            throw new IllegalArgumentException("letters and hints cannot both be empty");
        }
        var words = loadWords(lang, wordLength);
        return scan(words, 0, words.size(), new LetterPool(letters, strict), hints,
                isEffectivelyEmpty(letters), hasNoLetterHints(hints));
    }

    /// Intra-file split (axis B): word list scanned in `threads` contiguous
    /// chunks on virtual threads, merged in index order (== fileBaseline).
    public List<String> fileSplit(String lang, int wordLength, List<String> letters, List<Hint> hints, boolean strict, int threads) {
        if (wordLength <= 0 || (isEffectivelyEmpty(letters) && hasNoLetterHints(hints))) {
            throw new IllegalArgumentException("letters and hints cannot both be empty");
        }
        var words = loadWords(lang, wordLength);
        var pool = new LetterPool(letters, strict);
        boolean emptyLetters = isEffectivelyEmpty(letters);
        boolean emptyHints = hasNoLetterHints(hints);
        int n = Math.max(1, Math.min(threads, Math.max(1, words.size())));
        if (n <= 1) {
            return scan(words, 0, words.size(), pool, hints, emptyLetters, emptyHints);
        }
        int chunk = (words.size() + n - 1) / n; // ceil keeps chunks contiguous
        var futures = new ArrayList<Future<List<String>>>();
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int idx = 0; idx < n; idx++) {
                final int start = Math.min(idx * chunk, words.size());
                final int end = Math.min(start + chunk, words.size());
                futures.add(executor.submit(() ->
                        scan(words, start, end, pool, hints, emptyLetters, emptyHints)));
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

    /// A language code is a plain directory name under assets/. Anything else
    /// ("..", "/", an absolute path) would let `lang` escape the assets directory.
    private static final Pattern LANG = Pattern.compile("[a-z]{2,8}");

    public static boolean isValidLang(String lang) {
        return lang != null && LANG.matcher(lang).matches();
    }

    /// Word list for (lang, wordLength), cached. A missing file yields an empty
    /// list; an unsafe lang is rejected before any path is built.
    private List<WordEntry> loadWords(String lang, int wordLength) {
        if (!isValidLang(lang)) {
            throw new IllegalArgumentException("invalid lang: " + lang);
        }
        var key = lang + "/" + wordLength;
        return wordCache.computeIfAbsent(key, k -> {
            var file = assetsRoot.resolve(lang).resolve(wordLength + ".txt");
            try {
                return Files.readAllLines(file).stream()
                        .map(String::strip)
                        .filter(w -> !w.isEmpty())
                        .map(WordEntry::of)
                        .toList();
            } catch (NoSuchFileException e) {
                return List.of();
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        });
    }

    /// Normalize accents: "éàü" → "eau" (NFD + strip combining marks).
    static String normalize(String s) {
        return Normalizer.normalize(s, Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}", "");
    }

    /// Whether `word` can be built from `letters` (each used once in strict mode).
    /// Convenience form of LetterPool.matches for one word; the scans prepare the
    /// entry and the pool once instead.
    public static boolean matchesContent(String word, List<String> letters, boolean strict) {
        return new LetterPool(letters, strict).matches(WordEntry.of(word));
    }

    public static boolean matchesHints(String word, List<Hint> hints) {
        for (Hint hint : hints) {
            if (hint.letter() == null) continue;
            int pos = hint.position();
            // Positions are 1-indexed: one below 1 is out of range like one past
            // the end (charAt(-1) would throw).
            boolean outOfRange = pos < 1 || pos > word.length();
            if (!hint.excluded() && outOfRange) return false;
            if (outOfRange) continue;
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
