package com.lab.search.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;

import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

/// SEARCH_MODE: every mode returns exactly the baseline's words, and an unknown
/// mode is rejected (the application would fail at startup).
class SearchModeTest {

    private static final Path ASSETS = Path.of("../assets");

    private static List<String> file(SearchMode mode, int length, List<String> letters, List<Hint> hints, boolean strict) {
        return new WordSearchService(ASSETS, mode).searchInFile("fr", length, letters, hints, strict);
    }

    private static List<String> many(SearchMode mode, String letters, List<Hint> hints) {
        return new WordSearchService(ASSETS, mode).searchInManyFiles("fr", letters, hints);
    }

    @ParameterizedTest
    @EnumSource(SearchMode.class)
    void modesMatchBaseline(SearchMode mode) {
        var elisa = List.of("e", "l", "i", "s", "a");
        var fileCases = List.of(
                new Object[]{5, elisa, List.<Hint>of(), true},
                new Object[]{5, elisa, List.of(new Hint(1, "s", false)), false},
                new Object[]{7, List.<String>of(), List.of(new Hint(1, "a", false), new Hint(7, "e", true)), false});
        for (var c : fileCases) {
            @SuppressWarnings("unchecked") var letters = (List<String>) c[1];
            @SuppressWarnings("unchecked") var hints = (List<Hint>) c[2];
            var expected = file(SearchMode.BASELINE, (int) c[0], letters, hints, (boolean) c[3]);
            assertFalse(expected.isEmpty());
            assertEquals(expected, file(mode, (int) c[0], letters, hints, (boolean) c[3]));
        }
        for (var letters : List.of("guillaume", "artes")) {
            var hints = letters.equals("artes") ? List.of(new Hint(1, "a", false)) : List.<Hint>of();
            var expected = many(SearchMode.BASELINE, letters, hints);
            assertFalse(expected.isEmpty());
            assertEquals(expected, many(mode, letters, hints));
        }
    }

    @Test
    void parseAcceptsKnownModesInAnyCase() {
        assertEquals(SearchMode.PARALLEL, SearchMode.parse(null));
        assertEquals(SearchMode.PARALLEL, SearchMode.parse(" "));
        assertEquals(SearchMode.INDEXED, SearchMode.parse(" Indexed "));
        assertEquals(SearchMode.BASELINE, SearchMode.parse("baseline"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"dispatcher", "fast"})
    void parseRejectsUnknownModes(String value) {
        assertThrows(IllegalStateException.class, () -> SearchMode.parse(value));
    }
}
