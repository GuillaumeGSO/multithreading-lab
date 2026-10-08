package com.lab.search.service.strategy;

import com.lab.search.service.Hint;
import com.lab.search.service.LetterPool;
import com.lab.search.service.WordEntry;
import com.lab.search.service.WordSearchService;

import java.util.ArrayList;
import java.util.List;

public final class ScanStrategy implements SearchStrategy {

    @Override
    public String name() { return "scan"; }

    @Override
    public List<String> searchInFile(String lang, int wordLength, List<WordEntry> words,
                                     List<String> letters, List<Hint> hints,
                                     boolean strict, boolean emptyLetters, boolean emptyHints) {
        var pool = new LetterPool(letters, strict);
        List<String> results = new ArrayList<>();
        for (WordEntry e : words) {
            boolean ok = emptyHints ? pool.matches(e)
                    : emptyLetters ? WordSearchService.matchesHints(e.word(), hints)
                    : pool.matches(e) && WordSearchService.matchesHints(e.word(), hints);
            if (ok) results.add(e.word());
        }
        return results;
    }
}
