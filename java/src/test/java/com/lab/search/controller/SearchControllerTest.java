package com.lab.search.controller;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/// HTTP-level tests: request validation at the API boundary. Every request
/// outside the contract's bounds (openapi.yaml) must be a 400 ErrorResponse,
/// never a 5xx.
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class SearchControllerTest {

    private static final HttpClient CLIENT = HttpClient.newHttpClient();
    private static final String PIN = "{\"position\":1,\"letter\":\"a\"}";

    @Value("${local.server.port}")
    int port;

    private HttpResponse<String> post(String path, String body) throws Exception {
        var request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        return CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
    }

    static Stream<Arguments> invalidRequests() {
        return Stream.of(
                Arguments.of("/search/file", "{\"wordLength\":5,\"letters\":[\"a\"],\"hints\":[{\"position\":0,\"letter\":\"a\"}]}"),
                Arguments.of("/search/many", "{\"letters\":\"abc\",\"hints\":[{\"position\":-1,\"letter\":\"a\"}]}"),
                Arguments.of("/search/file", "{\"wordLength\":5,\"letters\":[\"a\"],\"hints\":[{\"position\":32,\"letter\":\"a\"}]}"),
                Arguments.of("/search/file", "{\"lang\":\"../../etc\",\"wordLength\":5,\"letters\":[\"a\"]}"),
                Arguments.of("/search/file", "{\"lang\":\"/etc\",\"wordLength\":5,\"letters\":[\"a\"]}"),
                Arguments.of("/search/many", "{\"lang\":\"xx\",\"letters\":\"abc\"}"),
                Arguments.of("/search/file", "{\"wordLength\":0,\"letters\":[\"a\"]}"),
                Arguments.of("/search/file", "{\"wordLength\":-1,\"letters\":[\"a\"]}"),
                Arguments.of("/search/file", "{\"wordLength\":32,\"letters\":[\"a\"]}"),
                Arguments.of("/search/file", "{\"letters\":[\"a\"]}"),
                Arguments.of("/search/file", "{\"wordLength\":5,\"letters\":[" + "\"a\",".repeat(32) + "\"a\"]}"),
                Arguments.of("/search/file", "{\"wordLength\":5,\"hints\":[" + (PIN + ",").repeat(31) + PIN + "]}"),
                Arguments.of("/search/many", "{\"letters\":\"" + "a".repeat(33) + "\"}"),
                Arguments.of("/search/many", "{\"hints\":[" + PIN + "]}"),
                Arguments.of("/search/many", "{\"letters\":[1]}"),
                Arguments.of("/search/many", "{\"letters\":123}"),
                Arguments.of("/search/file", "{\"wordLength\":5.5,\"letters\":[\"a\"]}"),
                Arguments.of("/search/file", "{\"wordLength\":5}"),
                Arguments.of("/search/file", "{not json"),
                Arguments.of("/search/many", "{not json"));
    }

    @ParameterizedTest
    @MethodSource("invalidRequests")
    void invalidRequestIs400(String path, String body) throws Exception {
        var res = post(path, body);
        assertEquals(400, res.statusCode(), res.body());
        assertTrue(res.body().matches("\\{\"error\":\".+\"}"), res.body());
    }

    @Test
    void validRequestsAtTheBoundsAre200() throws Exception {
        var file = post("/search/file", "{\"lang\":\"fr\",\"wordLength\":5,\"letters\":[\"e\",\"l\",\"i\",\"s\",\"a\"],"
                + "\"hints\":[{\"position\":1,\"letter\":\"s\"}]}");
        assertEquals(200, file.statusCode(), file.body());
        assertTrue(file.body().contains("\"count\":"), file.body());
        var many = post("/search/many", "{\"lang\":\"en\",\"letters\":\"" + "a".repeat(32) + "\"}");
        assertEquals(200, many.statusCode(), many.body());
    }
}
