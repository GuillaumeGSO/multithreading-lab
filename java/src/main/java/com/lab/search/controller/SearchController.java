package com.lab.search.controller;

import com.lab.search.api.HealthApi;
import com.lab.search.api.SearchApi;
import com.lab.search.api.model.ErrorResponse;
import com.lab.search.api.model.HealthResponse;
import com.lab.search.api.model.Lang;
import com.lab.search.api.model.SearchFileRequest;
import com.lab.search.api.model.SearchManyRequest;
import com.lab.search.api.model.SearchResponse;
import com.lab.search.service.Hint;
import com.lab.search.service.WordSearchService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

/// Implements the HealthApi and SearchApi interfaces generated from openapi.yaml:
/// routes, request bodies and response types all come from the contract.
@RestController
public class SearchController implements HealthApi, SearchApi {

    private static final Logger log = LoggerFactory.getLogger(SearchController.class);

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
                Objects.requireNonNullElse(req.getLang(), Lang.FR).getValue(),
                Objects.requireNonNullElse(req.getWordLength(), 0),
                Objects.requireNonNullElse(req.getLetters(), List.of()),
                toHints(req.getHints()),
                Boolean.TRUE.equals(req.getStrict()));
        return ResponseEntity.ok(new SearchResponse(words, words.size()));
    }

    @Override
    public ResponseEntity<SearchResponse> searchMany(SearchManyRequest req) {
        var words = service.searchInManyFiles(
                Objects.requireNonNullElse(req.getLang(), Lang.FR).getValue(),
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

    /// Constraint violations generated from openapi.yaml (@Min/@Max/@Size/@NotNull).
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleInvalid(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(SearchController::describe)
                .collect(Collectors.joining("; "));
        return ResponseEntity.badRequest().body(new ErrorResponse(message));
    }

    /// Malformed JSON, a wrong field type or an unknown enum value. The parser's
    /// own message names internal classes, so it is not echoed to the client.
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ErrorResponse> handleUnreadable(HttpMessageNotReadableException e) {
        return ResponseEntity.badRequest().body(new ErrorResponse(
                "malformed JSON body, wrong field type or unknown enum value (lang: fr, en)"));
    }

    /// Requests the search algorithm itself rejects (no letters and no hints).
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponse> handleBadRequest(IllegalArgumentException e) {
        return ResponseEntity.badRequest().body(new ErrorResponse(e.getMessage()));
    }

    /// Spring's own web exceptions keep their 4xx status; anything else is a
    /// server fault: logged, answered without internal details.
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception e) {
        if (e instanceof org.springframework.web.ErrorResponse web && web.getStatusCode().is4xxClientError()) {
            return ResponseEntity.status(web.getStatusCode()).body(new ErrorResponse(web.getBody().getTitle()));
        }
        log.error("unexpected error", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(new ErrorResponse("internal error"));
    }

    private static String describe(FieldError error) {
        return error.getField() + ": " + error.getDefaultMessage();
    }
}
