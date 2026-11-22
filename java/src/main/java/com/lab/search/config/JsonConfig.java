package com.lab.search.config;

import com.fasterxml.jackson.annotation.JsonSetter;
import com.fasterxml.jackson.annotation.Nulls;
import com.lab.search.api.model.Hint;
import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.cfg.CoercionAction;
import tools.jackson.databind.cfg.CoercionInputShape;
import tools.jackson.databind.type.LogicalType;

/// Request bodies follow the contract's types strictly. By default Jackson would
/// turn `"letters": 123` into the string "123", truncate `"wordLength": 5.5` to 5,
/// read `"strict": 0` as false and take `"strict": null` as "absent". All of
/// these are rejected instead (answered with 400).
@Configuration
public class JsonConfig {

    @Bean
    JsonMapperBuilderCustomizer strictScalarTypes() {
        return builder -> builder
                .withCoercionConfig(LogicalType.Textual, cfg -> cfg
                        .setCoercion(CoercionInputShape.Integer, CoercionAction.Fail)
                        .setCoercion(CoercionInputShape.Float, CoercionAction.Fail)
                        .setCoercion(CoercionInputShape.Boolean, CoercionAction.Fail))
                .withCoercionConfig(LogicalType.Integer, cfg -> cfg
                        .setCoercion(CoercionInputShape.Float, CoercionAction.Fail))
                .withCoercionConfig(LogicalType.Boolean, cfg -> cfg
                        .setCoercion(CoercionInputShape.Integer, CoercionAction.Fail)
                        .setCoercion(CoercionInputShape.String, CoercionAction.Fail))
                // No field or array element may be null...
                .changeDefaultNullHandling(n -> JsonSetter.Value.forValueNulls(Nulls.FAIL, Nulls.FAIL))
                // ...except Hint.letter, the one `nullable: true` field in openapi.yaml.
                .addMixIn(Hint.class, NullableHintLetter.class);
    }

    abstract static class NullableHintLetter {
        @JsonSetter(nulls = Nulls.SET)
        abstract void setLetter(String letter);
    }
}
