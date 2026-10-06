package com.lab.search.controller;

import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.dataformat.yaml.YAMLMapper;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;

/// Serves the API contract — the repository's openapi.yaml, packaged on the
/// classpath at build time — verbatim as YAML and converted to JSON, plus a
/// Swagger UI page at /docs that reads /openapi.json. Nothing is generated from code.
@RestController
public class OpenApiController {

    private final String yaml;
    private final String json;

    public OpenApiController() {
        try (var in = new ClassPathResource("openapi/openapi.yaml").getInputStream()) {
            this.yaml = new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("openapi.yaml missing from the classpath", e);
        }
        this.json = JsonMapper.shared().writeValueAsString(new YAMLMapper().readTree(yaml));
    }

    @GetMapping(value = "/openapi.json", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> json() {
        return ResponseEntity.ok(json);
    }

    @GetMapping(value = "/openapi.yaml", produces = "application/yaml")
    public ResponseEntity<String> yaml() {
        return ResponseEntity.ok(yaml);
    }

    @GetMapping(value = "/docs", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> docs() {
        return ResponseEntity.ok(SWAGGER_UI_HTML);
    }

    // Swagger UI assets come from the swagger-ui webjar (version resolved by
    // webjars-locator-lite), so /docs works without internet access.
    private static final String SWAGGER_UI_HTML = """
            <!DOCTYPE html>
            <html>
            <head>
              <title>Word Search API</title>
              <meta charset="utf-8"/>
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <link rel="stylesheet" href="/webjars/swagger-ui/swagger-ui.css">
            </head>
            <body>
            <div id="swagger-ui"></div>
            <script src="/webjars/swagger-ui/swagger-ui-bundle.js"></script>
            <script>
              window.onload = () => SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" });
            </script>
            </body>
            </html>
            """;
}
