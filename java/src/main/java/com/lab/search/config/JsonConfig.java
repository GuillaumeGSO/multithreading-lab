package com.lab.search.config;

import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.cfg.CoercionAction;
import tools.jackson.databind.cfg.CoercionInputShape;
import tools.jackson.databind.type.LogicalType;

/// Request bodies follow the contract's types strictly: by default Jackson
/// would turn `"letters": 123` into the string "123" and truncate
/// `"wordLength": 5.5` to 5. Both are rejected instead (answered with 400).
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
                        .setCoercion(CoercionInputShape.Float, CoercionAction.Fail));
    }
}
