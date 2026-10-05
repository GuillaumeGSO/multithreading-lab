package com.lab.search.model;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "Word search result")
public record SearchResponse(
        @Schema(description = "Matching words in scan order (longest-first for /search/many)") List<String> words,
        @Schema(description = "Total number of matching words") int count
) {
    public static SearchResponse of(List<String> words) {
        return new SearchResponse(words, words.size());
    }
}
