package com.lab.search.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

/// `inverted` defaults to false when absent in JSON (Jackson uses false for a missing boolean).
@Schema(description = "Positional constraint on a word")
public record Hint(
        @Schema(description = "1-indexed position of the constraint", example = "3") int pos,
        @Schema(description = "Expected character at pos; null means no character constraint", example = "e", nullable = true) String car,
        @JsonProperty("inverted") @Schema(description = "When true, the character must NOT appear at pos", defaultValue = "false") boolean inverted
) {
}
