package com.lab.search.service;

import com.lab.search.model.Hint;
import com.lab.search.model.SearchResponse;
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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

@Service
public class WordSearchService {

    private final Path assetsRoot;
    private final ConcurrentHashMap<String, List<String>> wordCache = new ConcurrentHashMap<>();

    public WordSearchService() {
        String root = System.getenv("ASSETS_ROOT");
        this.assetsRoot = Path.of(root != null ? root : "assets");
    }

    WordSearchService(Path assetsRoot) {
        this.assetsRoot = assetsRoot;
    }

    public SearchResponse searchInFile(String lang, int nbCar, List<String> lstCar, List<Hint> lstHint, boolean strict) {
        if (isEffectivelyEmpty(lstCar) && hasNoCarHints(lstHint)) {
            throw new IllegalArgumentException("Either lst_car or lst_hint must be provided");
        }

        List<String> words = loadWords(lang, nbCar);
        List<String> results = new ArrayList<>();

        for (String word : words) {
            boolean contentOk = isEffectivelyEmpty(lstCar) || matchesContent(word, lstCar, strict);
            boolean hintOk = hasNoCarHints(lstHint) || matchesHints(word, lstHint);
            if (contentOk && hintOk) {
                results.add(word);
            }
        }

        return SearchResponse.of(results);
    }

    public SearchResponse searchInManyFiles(String lang, String cars, List<Hint> lstHint) {
        if (cars == null || cars.isEmpty()) {
            throw new IllegalArgumentException("cars must be provided");
        }

        int minLen = lstHint.stream()
                .filter(h -> h.car() != null && !h.inverted())
                .mapToInt(Hint::pos)
                .max()
                .orElse(1);

        // Submit one task per length (longest first), collect in order
        int maxLen = cars.length();
        List<Future<List<String>>> futures = new ArrayList<>();

        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int len = maxLen; len >= minLen; len--) {
                final int nbCar = len;
                futures.add(executor.submit(() -> {
                    List<String> lstCar = new ArrayList<>(List.of(cars.split("")));
                    return searchInFile(lang, nbCar, lstCar, lstHint, false).words();
                }));
            }
        }

        List<String> results = new ArrayList<>();
        for (Future<List<String>> f : futures) {
            try {
                results.addAll(f.get());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException(e);
            } catch (ExecutionException e) {
                // skip lengths with no word file
            }
        }

        return SearchResponse.of(results);
    }

    // --- helpers ---

    private List<String> loadWords(String lang, int nbCar) {
        String key = lang + "/" + nbCar;
        return wordCache.computeIfAbsent(key, k -> {
            Path file = assetsRoot.resolve(lang).resolve(nbCar + ".txt");
            try {
                return Files.readAllLines(file);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        });
    }

    /** Normalize accents: "éàü" → "eau" (NFD + strip combining marks). */
    private static String normalize(String s) {
        return Normalizer.normalize(s, Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}", "");
    }

    static boolean matchesContent(String word, List<String> lstCar, boolean strict) {
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

    static boolean matchesHints(String word, List<Hint> lstHint) {
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

    static boolean isEffectivelyEmpty(List<String> lst) {
        return lst == null || lst.stream().allMatch(s -> s == null || s.isEmpty());
    }

    static boolean hasNoCarHints(List<Hint> lst) {
        return lst == null || lst.stream().allMatch(h -> h.car() == null || h.car().isEmpty());
    }
}
