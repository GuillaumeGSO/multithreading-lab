package com.lab.search.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public record SearchFileRequest(
        String lang,
        @JsonProperty("nb_car") int nbCar,
        @JsonProperty("lst_car") List<String> lstCar,
        @JsonProperty("lst_hint") List<Hint> lstHint,
        boolean strict
) {
    public SearchFileRequest {
        if (lang == null) lang = "fr";
        if (lstCar == null) lstCar = List.of();
        if (lstHint == null) lstHint = List.of();
    }
}
