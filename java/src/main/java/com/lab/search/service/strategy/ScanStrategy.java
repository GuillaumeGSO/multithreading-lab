package com.lab.search.service.strategy;

import com.lab.search.service.Hint;
import com.lab.search.service.WordSearchService;

import java.util.ArrayList;
import java.util.List;

public final class ScanStrategy implements SearchStrategy {

    @Override
    public String name() { return "scan"; }

    @Override
    public List<String> searchInFile(String lang, int wordLength, List<String> words,
                                     List<String> letters, List<Hint> hints,
                                     boolean strict, boolean emptyLetters, boolean emptyHints) {
        List<String> results = new ArrayList<>();
        for (String word : words) {
            if ((emptyLetters || WordSearchService.matchesContent(word, letters, strict)) &&
                (emptyHints || WordSearchService.matchesHints(word, hints)))
                results.add(word);
        }
        return results;
    }
}
