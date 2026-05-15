package com.lab.search.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public record SearchManyRequest(
        String lang,
        String cars,
        @JsonProperty("lst_hint") List<Hint> lstHint
) {
    public SearchManyRequest {
        if (lang == null) lang = "fr";
        if (lstHint == null) lstHint = List.of();
    }
}
