package com.lab.search.service.strategy;

import com.lab.search.service.Hint;
import com.lab.search.service.WordEntry;
import java.util.List;

public interface SearchStrategy {
    String name();

    /**
     * Search a single word-length file. Returns words in word-list order.
     * words is already loaded by WordSearchService — strategies never touch the filesystem.
     */
    List<String> searchInFile(String lang, int wordLength,
                              List<WordEntry> words,
                              List<String> letters, List<Hint> hints,
                              boolean strict,
                              boolean emptyLetters, boolean emptyHints);
}
