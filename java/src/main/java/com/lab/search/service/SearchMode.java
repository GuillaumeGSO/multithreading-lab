package com.lab.search.service;

import java.util.Arrays;
import java.util.Locale;
import java.util.stream.Collectors;

/// The implementation the live API serves, chosen by `SEARCH_MODE`. Every
/// language in this lab gives the modes the same meaning:
///
/// - `baseline`: single-threaded scan (`/many` scans the lengths one after another)
/// - `parallel`: scan split into `SPLIT_DEGREE` chunks per file on virtual threads;
///   `/many` also fans out one virtual thread per length (the default)
/// - `indexed`: index dispatcher for `/file` (positional index when a pinned hint
///   exists, scan otherwise); `/many` is the single-threaded scan
public enum SearchMode {
    BASELINE, PARALLEL, INDEXED;

    public static final SearchMode DEFAULT = PARALLEL;

    /// Parses a `SEARCH_MODE` value (null or blank means the default). An unknown
    /// value throws, so a typo fails at startup instead of silently serving a
    /// different mode.
    public static SearchMode parse(String value) {
        if (value == null || value.isBlank()) return DEFAULT;
        var name = value.trim().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(m -> m.name().equals(name))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException("unknown SEARCH_MODE '" + value.trim()
                        + "'; expected one of " + Arrays.stream(values())
                        .map(m -> m.name().toLowerCase(Locale.ROOT))
                        .collect(Collectors.joining(", "))));
    }
}
