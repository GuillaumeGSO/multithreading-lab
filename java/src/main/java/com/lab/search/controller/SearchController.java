package com.lab.search.controller;

import com.lab.search.api.HealthApi;
import com.lab.search.api.SearchApi;
import com.lab.search.api.model.ErrorResponse;
import com.lab.search.api.model.HealthResponse;
import com.lab.search.api.model.SearchFileRequest;
import com.lab.search.api.model.SearchManyRequest;
import com.lab.search.api.model.SearchResponse;
import com.lab.search.service.Hint;
import com.lab.search.service.WordSearchService;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Objects;

/// Implements the HealthApi and SearchApi interfaces generated from openapi.yaml:
/// routes, request bodies and response types all come from the contract.
@RestController
public class SearchController implements HealthApi, SearchApi {

    private final WordSearchService service;

    public SearchController(WordSearchService service) {
        this.service = service;
    }

    @Override
    public ResponseEntity<HealthResponse> health() {
        return ResponseEntity.ok(new HealthResponse("ok"));
    }

    @Override
    public ResponseEntity<SearchResponse> searchFile(SearchFileRequest req) {
        var words = service.searchInFile(
                Objects.requireNonNullElse(req.getLang(), "fr"),
                Objects.requireNonNullElse(req.getWordLength(), 0),
                Objects.requireNonNullElse(req.getLetters(), List.of()),
                toHints(req.getHints()),
                Boolean.TRUE.equals(req.getStrict()));
        return ResponseEntity.ok(new SearchResponse(words, words.size()));
    }

    @Override
    public ResponseEntity<SearchResponse> searchMany(SearchManyRequest req) {
        var words = service.searchInManyFiles(
                Objects.requireNonNullElse(req.getLang(), "fr"),
                req.getLetters(),
                toHints(req.getHints()));
        return ResponseEntity.ok(new SearchResponse(words, words.size()));
    }

    private static List<Hint> toHints(List<com.lab.search.api.model.Hint> hints) {
        if (hints == null) return List.of();
        return hints.stream()
                .map(h -> new Hint(
                        Objects.requireNonNullElse(h.getPosition(), 0),
                        h.getLetter(),
                        Boolean.TRUE.equals(h.getExcluded())))
                .toList();
    }

    @ExceptionHandler({IllegalArgumentException.class, HttpMessageNotReadableException.class})
    public ResponseEntity<ErrorResponse> handleBadRequest(Exception e) {
        return ResponseEntity.badRequest().body(new ErrorResponse(e.getMessage()));
    }
}
