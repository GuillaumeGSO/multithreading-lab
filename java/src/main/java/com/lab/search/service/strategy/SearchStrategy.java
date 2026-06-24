package com.lab.search.service.strategy;

import com.lab.search.model.Hint;
import java.util.List;

public interface SearchStrategy {
    String name();

    /**
     * Search a single word-length file. Returns words in word-list order.
     * words is already loaded by WordSearchService — strategies never touch the filesystem.
     */
    List<String> searchInFile(String lang, int nbCar,
                              List<String> words,
                              List<String> lstCar, List<Hint> lstHint,
                              boolean strict,
                              boolean emptyCars, boolean emptyHints);
}
