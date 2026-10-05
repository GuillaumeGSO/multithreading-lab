package com.lab.search.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "Request body for /search/file")
public record SearchFileRequest(
        @Schema(description = "Language code (dictionary subfolder)", example = "fr", defaultValue = "fr") String lang,
        @JsonProperty("nb_car") @Schema(description = "Exact word length to search for", example = "5") int nbCar,
        @JsonProperty("lst_car") @Schema(description = "Available letters; empty means no letter-pool constraint") List<String> lstCar,
        @JsonProperty("lst_hint") @Schema(description = "Positional constraints applied after the letter-pool filter") List<Hint> lstHint,
        @Schema(description = "Each letter may only be used once (Scrabble-style)", defaultValue = "false") boolean strict
) {
    public SearchFileRequest {
        if (lang == null) lang = "fr";
        if (lstCar == null) lstCar = List.of();
        if (lstHint == null) lstHint = List.of();
    }
}
