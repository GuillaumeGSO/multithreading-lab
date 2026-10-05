package com.lab.search.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "Request body for /search/many")
public record SearchManyRequest(
        @Schema(description = "Language code (dictionary subfolder)", example = "fr", defaultValue = "fr") String lang,
        @Schema(description = "Available letters as a string; max word length equals len(cars)", example = "artes") String cars,
        @JsonProperty("lst_hint") @Schema(description = "Positional constraints applied across every length scanned") List<Hint> lstHint
) {
    public SearchManyRequest {
        if (lang == null) lang = "fr";
        if (lstHint == null) lstHint = List.of();
    }
}
