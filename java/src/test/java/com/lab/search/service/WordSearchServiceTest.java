package com.lab.search.service;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.Arrays;
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
    @Test void listAllNull() { assertTrue(WordSearchService.isEffectivelyEmpty(Arrays.asList(null, null))); }
    @Test void listHasValues() { assertFalse(WordSearchService.isEffectivelyEmpty(List.of("a", "b"))); }

    // --- hasNoLetterHints ---

    @Test void hintListEmpty() { assertTrue(WordSearchService.hasNoLetterHints(List.of())); }
    @Test void hintListNoLetter() { assertTrue(WordSearchService.hasNoLetterHints(List.of(new Hint(1, null, false), new Hint(2, null, false)))); }
    @Test void hintListHasLetter() { assertFalse(WordSearchService.hasNoLetterHints(List.of(new Hint(1, "a", false)))); }

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
    @Test void hintExcludedMatchRejects() {
        // "salut" has 's' at pos 1 → excluded hint rejects it
        assertFalse(WordSearchService.matchesHints("salut", List.of(new Hint(1, "s", true))));
    }
    @Test void hintExcludedNoMatchAccepts() {
        // "salut" does not have 'a' at pos 1 → excluded hint passes
        assertTrue(WordSearchService.matchesHints("salut", List.of(new Hint(1, "a", true))));
    }
    @Test void hintPositionOutOfRangeNormalExcludes() {
        // word length 3, hint at pos 4 → can never be satisfied
        assertFalse(WordSearchService.matchesHints("mot", List.of(new Hint(4, "a", false))));
    }
    @Test void hintPositionOutOfRangeExcludedIncludes() {
        // word length 3, excluded hint at pos 4 → trivially satisfied
        assertTrue(WordSearchService.matchesHints("mot", List.of(new Hint(4, "a", true))));
    }
    @Test void hintLetterNullIgnored() {
        assertTrue(WordSearchService.matchesHints("bonjour", List.of(new Hint(1, null, false))));
    }
    @Test void hintMultipleAllMatch() {
        assertTrue(WordSearchService.matchesHints("salut", List.of(new Hint(1, "s", false), new Hint(5, "t", false))));
    }
    @Test void hintMultipleOneFails() {
        assertFalse(WordSearchService.matchesHints("salut", List.of(new Hint(1, "s", false), new Hint(5, "x", false))));
    }

    // --- searchInFile (integration — uses real assets) ---

    @Test void searchFileRaisesEmptyLettersAndHints() {
        assertThrows(IllegalArgumentException.class,
                () -> service.searchInFile("fr", 5, List.of(), List.of(), false));
    }
    @Test void searchFileMissingFileReturnsEmpty() {
        // wordLength=99 → no such file → empty (mirrors the Python reference)
        assertEquals(List.of(), service.searchInFile("fr", 99, List.of("a", "b", "c"), List.of(), false));
    }

    // --- input guards ---

    @Test void unsafeLangIsRejected() {
        for (String lang : List.of("../../etc", "/etc", "fr/../en", "")) {
            assertFalse(WordSearchService.isValidLang(lang), lang);
            assertThrows(IllegalArgumentException.class,
                    () -> service.searchInFile(lang, 5, List.of("a"), List.of(), false), lang);
        }
        assertTrue(WordSearchService.isValidLang("fr"));
    }
    @Test void hintPositionBelowOneIsOutOfRange() {
        for (int position : new int[]{0, -1}) {
            assertFalse(WordSearchService.matchesHints("abc", List.of(new Hint(position, "a", false))));
            assertTrue(WordSearchService.matchesHints("abc", List.of(new Hint(position, "a", true))));
        }
    }
    @Test void searchFileByContent() {
        List<String> r = service.searchInFile("fr", 5, List.of("e","l","i","s","a"), List.of(), true);
        assertEquals(8, r.size());
        assertTrue(r.contains("ailes"));
    }
    @Test void searchFileByHint() {
        List<String> r = service.searchInFile("fr", 5, List.of(),
                List.of(new Hint(1, "s", false), new Hint(3, "a", false), new Hint(5, "e", false)), false);
        assertEquals(8, r.size());
        assertTrue(r.contains("slave"));
    }
    @Test void searchFileContentAndHint() {
        List<String> r = service.searchInFile("fr", 5, List.of("e","l","i","s","a"),
                List.of(new Hint(1, "l", false), new Hint(5, "s", false)), false);
        assertEquals(11, r.size());
    }

    // --- searchInManyFiles (integration — uses real assets) ---

    @Test void searchManyAllLengths() {
        List<String> r = service.searchInManyFiles("fr", "guillaume", List.of());
        assertEquals(494, r.size());
    }
    @Test void searchManySkipsShortWordsWithNormalHint() {
        // Hint at pos 4 → words shorter than 4 letters must be excluded
        List<String> r = service.searchInManyFiles("fr", "guillaume",
                List.of(new Hint(4, "a", false)));
        assertTrue(r.stream().allMatch(w -> w.length() >= 4));
    }
    @Test void searchManyExcludedHintIncludesShortWords() {
        // Excluded hint at pos 4 → words shorter than 4 letters are still included
        List<String> r = service.searchInManyFiles("fr", "guillaume",
                List.of(new Hint(4, "z", true)));
        assertTrue(r.stream().anyMatch(w -> w.length() < 4));
    }

    // --- parallel variants must match the baseline byte-for-byte (same order) ---

    @Test void fileSplitMatchesBaselineForAllDegrees() {
        record Case(int len, List<String> letters, List<Hint> hints, boolean strict) {}
        List<Case> cases = List.of(
                new Case(5, List.of("e","l","i","s","a"), List.of(), true),
                new Case(5, List.of("e","l","i","s","a"), List.of(), false),
                new Case(5, List.of(), List.of(new Hint(1,"s",false), new Hint(3,"a",false), new Hint(5,"e",false)), false),
                new Case(5, List.of("e","l","i","s","a"), List.of(new Hint(1,"l",false), new Hint(5,"s",false)), false)
        );
        for (Case c : cases) {
            List<String> want = service.fileBaseline("fr", c.len(), c.letters(), c.hints(), c.strict());
            for (int threads : new int[]{1, 2, 3, 5}) {
                assertEquals(want, service.fileSplit("fr", c.len(), c.letters(), c.hints(), c.strict(), threads),
                        "fileSplit(threads=" + threads + ") must equal fileBaseline");
            }
        }
    }

    @Test void manyParallelMatchesBaselineForAllDegrees() {
        List<List<Hint>> hintSets = List.of(
                List.of(),
                List.of(new Hint(4, "a", false), new Hint(1, "a", true))
        );
        for (List<Hint> hints : hintSets) {
            List<String> want = service.manyBaseline("fr", "guillaume", hints);
            assertEquals(want, service.manyFanout("fr", "guillaume", hints));
            for (int threads : new int[]{1, 2, 3}) {
                assertEquals(want, service.manyNested("fr", "guillaume", hints, threads),
                        "manyNested(threads=" + threads + ") must equal manyBaseline");
            }
        }
    }

    // --- IndexedStrategy equivalence: must return byte-identical results to scan ---

    @Test void indexedMatchesScanForPinnedHints() {
        List<Hint> hints = List.of(new Hint(1, "s", false), new Hint(3, "a", false), new Hint(5, "e", false));
        assertEquals(service.fileBaseline("fr", 5, List.of(), hints, false),
                     service.fileIndexed ("fr", 5, List.of(), hints, false));
    }

    @Test void indexedMatchesScanForContentAndHint() {
        List<Hint> hints = List.of(new Hint(1, "l", false), new Hint(5, "s", false));
        List<String> letters = List.of("e","l","i","s","a");
        assertEquals(service.fileBaseline("fr", 5, letters, hints, false),
                     service.fileIndexed ("fr", 5, letters, hints, false));
    }

    @Test void indexedMatchesScanForLettersOnly() {
        List<String> letters = List.of("e","l","i","s","a");
        assertEquals(service.fileBaseline("fr", 5, letters, List.of(), true),
                     service.fileIndexed ("fr", 5, letters, List.of(), true));
    }

    // --- fileDispatch routing ---

    @Test void fileDispatchUsesIndexedWhenPinnedHint() {
        List<Hint> hints = List.of(new Hint(1, "s", false), new Hint(5, "e", false));
        assertEquals(service.fileIndexed ("fr", 5, List.of(), hints, false),
                     service.fileDispatch("fr", 5, List.of(), hints, false));
    }

    @Test void fileDispatchUsesScanWhenNoPin() {
        List<Hint> hints = List.of(new Hint(1, "x", true));
        List<String> letters = List.of("e","l","i","s","a");
        assertEquals(service.fileBaseline("fr", 5, letters, hints, false),
                     service.fileDispatch("fr", 5, letters, hints, false));
    }

    // --- IndexedStrategy edge cases ---

    @Test void indexedPinnedBeyondLengthReturnsEmpty() {
        List<String> result = service.fileIndexed("fr", 5, List.of(),
                List.of(new Hint(10, "a", false)), false);
        assertTrue(result.isEmpty());
    }

    @Test void indexedCacheReusedAcrossCalls() {
        List<Hint> hints = List.of(new Hint(1, "s", false));
        assertEquals(service.fileIndexed("fr", 5, List.of(), hints, false),
                     service.fileIndexed("fr", 5, List.of(), hints, false));
    }
}
