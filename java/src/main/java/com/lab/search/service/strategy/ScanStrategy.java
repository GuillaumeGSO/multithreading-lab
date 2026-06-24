package com.lab.search.service.strategy;

import com.lab.search.model.Hint;
import com.lab.search.service.WordSearchService;

import java.util.ArrayList;
import java.util.List;

public final class ScanStrategy implements SearchStrategy {

    @Override
    public String name() { return "scan"; }

    @Override
    public List<String> searchInFile(String lang, int nbCar, List<String> words,
                                     List<String> lstCar, List<Hint> lstHint,
                                     boolean strict, boolean emptyCars, boolean emptyHints) {
        List<String> results = new ArrayList<>();
        for (String word : words) {
            if ((emptyCars || WordSearchService.matchesContent(word, lstCar, strict)) &&
                (emptyHints || WordSearchService.matchesHints(word, lstHint)))
                results.add(word);
        }
        return results;
    }
}
