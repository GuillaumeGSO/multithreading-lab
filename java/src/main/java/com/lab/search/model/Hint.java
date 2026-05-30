package com.lab.search.model;

import com.fasterxml.jackson.annotation.JsonProperty;

/// `inverted` defaults to false when absent in JSON (Jackson uses false for a missing boolean).
public record Hint(
        int pos,
        String car,
        @JsonProperty("inverted") boolean inverted
) {
}
