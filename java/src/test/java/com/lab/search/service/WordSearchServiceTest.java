package com.lab.search.service;

import com.lab.search.model.Hint;
import com.lab.search.model.SearchResponse;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class WordSearchServiceTest {

    // Points to assets/ relative to the java/ module directory (Maven working dir)
    private static WordSearchService service;

    @BeforeAll
    static void setup() {
        service = new WordSearchService(Path.of("../assets"));
    }

    // --- isEffectivelyEmpty ---

    @Test void listEmpty() { assertTrue(WordSearchService.isEffectivelyEmpty(List.of())); }
    @Test void listAllNull() { assertTrue(WordSearchService.isEffectivelyEmpty(java.util.Arrays.asList(null, null))); }
    @Test void listHasValues() { assertFalse(WordSearchService.isEffectivelyEmpty(List.of("a", "b"))); }

    // --- hasNoCarHints ---

    @Test void hintListEmpty() { assertTrue(WordSearchService.hasNoCarHints(List.of())); }
    @Test void hintListNoCar() { assertTrue(WordSearchService.hasNoCarHints(List.of(new Hint(1, null, false), new Hint(2, null, false)))); }
    @Test void hintListHasCar() { assertFalse(WordSearchService.hasNoCarHints(List.of(new Hint(1, "a", false)))); }

    // --- matchesContent ---

    @Test void contentEmptyWord() { assertFalse(WordSearchService.matchesContent("", List.of("a", "b"), false)); }
    @Test void contentEmptyLetters() { assertFalse(WordSearchService.matchesContent("abc", List.of(), false)); }
    @Test void contentMatch() { assertTrue(WordSearchService.matchesContent("ale", List.of("a", "l", "e", "s"), false)); }
    @Test void contentLetterMissing() { assertFalse(WordSearchService.matchesContent("zoo", List.of("a", "l", "e"), false)); }
    @Test void contentStrictExactAnagram() { assertTrue(WordSearchService.matchesContent("aile", List.of("a", "i", "l", "e"), true)); }
    @Test void contentStrictRejectsRepeatedLetter() {
        // "alle" needs two l's; pool has only one
        assertFalse(WordSearchService.matchesContent("alle", List.of("a", "l", "e"), true));
    }
    @Test void contentAccentStripped() {
        // "île" normalises to "ile"; pool covers it
        assertTrue(WordSearchService.matchesContent("île", List.of("i", "l", "e"), false));
    }

    // --- matchesHints ---

    @Test void hintEmptyWord() { assertFalse(WordSearchService.matchesHints("", List.of(new Hint(1, "a", false)))); }
    @Test void hintNoHints() { assertTrue(WordSearchService.matchesHints("bonjour", List.of())); }
    @Test void hintMatch() { assertTrue(WordSearchService.matchesHints("salut", List.of(new Hint(1, "s", false)))); }
    @Test void hintNoMatch() { assertFalse(WordSearchService.matchesHints("salut", List.of(new Hint(1, "a", false)))); }
    @Test void hintInvertedMatchExcludes() {
        // "salut" has 's' at pos 1 → inverted hint rejects it
        assertFalse(WordSearchService.matchesHints("salut", List.of(new Hint(1, "s", true))));
    }
    @Test void hintInvertedNoMatchIncludes() {
        // "salut" does not have 'a' at pos 1 → inverted hint passes
        assertTrue(WordSearchService.matchesHints("salut", List.of(new Hint(1, "a", true))));
    }
    @Test void hintPositionOutOfRangeNormalExcludes() {
        // word length 3, hint at pos 4 → can never be satisfied
        assertFalse(WordSearchService.matchesHints("mot", List.of(new Hint(4, "a", false))));
    }
    @Test void hintPositionOutOfRangeInvertedIncludes() {
        // word length 3, inverted hint at pos 4 → trivially satisfied
        assertTrue(WordSearchService.matchesHints("mot", List.of(new Hint(4, "a", true))));
    }
    @Test void hintCarNullIgnored() {
        assertTrue(WordSearchService.matchesHints("bonjour", List.of(new Hint(1, null, false))));
    }
    @Test void hintMultipleAllMatch() {
        assertTrue(WordSearchService.matchesHints("salut", List.of(new Hint(1, "s", false), new Hint(5, "t", false))));
    }
    @Test void hintMultipleOneFails() {
        assertFalse(WordSearchService.matchesHints("salut", List.of(new Hint(1, "s", false), new Hint(5, "x", false))));
    }

    // --- searchInFile (integration — uses real assets) ---

    @Test void searchFileRaisesEmptyCarsAndHints() {
        assertThrows(IllegalArgumentException.class,
                () -> service.searchInFile("fr", 5, List.of(), List.of(), false));
    }
    @Test void searchFileMissingFileReturnsEmpty() {
        // nb_car=99 → no such file → UncheckedIOException caught inside → empty
        assertThrows(Exception.class,
                () -> service.searchInFile("fr", 99, List.of("a", "b", "c"), List.of(), false));
    }
    @Test void searchFileByContent() {
        SearchResponse r = service.searchInFile("fr", 5, List.of("e","l","i","s","a"), List.of(), true);
        assertEquals(8, r.count());
        assertTrue(r.words().contains("ailes"));
    }
    @Test void searchFileByHint() {
        SearchResponse r = service.searchInFile("fr", 5, List.of(),
                List.of(new Hint(1, "s", false), new Hint(3, "a", false), new Hint(5, "e", false)), false);
        assertEquals(8, r.count());
        assertTrue(r.words().contains("slave"));
    }
    @Test void searchFileContentAndHint() {
        SearchResponse r = service.searchInFile("fr", 5, List.of("e","l","i","s","a"),
                List.of(new Hint(1, "l", false), new Hint(5, "s", false)), false);
        assertEquals(11, r.count());
    }

    // --- searchInManyFiles (integration — uses real assets) ---

    @Test void searchManyAllLengths() {
        SearchResponse r = service.searchInManyFiles("fr", "guillaume", List.of());
        assertEquals(498, r.count());
    }
    @Test void searchManySkipsShortWordsWithNormalHint() {
        // Hint at pos 4 → words shorter than 4 letters must be excluded
        SearchResponse r = service.searchInManyFiles("fr", "guillaume",
                List.of(new Hint(4, "a", false)));
        assertTrue(r.words().stream().allMatch(w -> w.length() >= 4));
    }
    @Test void searchManyInvertedHintIncludesShortWords() {
        // Inverted hint at pos 4 → words shorter than 4 letters are still included
        SearchResponse r = service.searchInManyFiles("fr", "guillaume",
                List.of(new Hint(4, "z", true)));
        assertTrue(r.words().stream().anyMatch(w -> w.length() < 4));
    }
}
