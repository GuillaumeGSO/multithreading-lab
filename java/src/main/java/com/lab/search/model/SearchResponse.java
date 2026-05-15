package com.lab.search.model;

import java.util.List;

public record SearchResponse(List<String> words, int count) {
    public static SearchResponse of(List<String> words) {
        return new SearchResponse(words, words.size());
    }
}
