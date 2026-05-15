package com.lab.search.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record Hint(
        int pos,
        String car,
        @JsonProperty("inverted") boolean inverted
) {
    public Hint {
        // inverted defaults to false when absent in JSON (Jackson uses false for missing boolean)
    }
}
