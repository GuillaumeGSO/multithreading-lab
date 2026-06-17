package com.lab.search.controller;

import com.lab.search.model.SearchFileRequest;
import com.lab.search.model.SearchManyRequest;
import com.lab.search.model.SearchResponse;
import com.lab.search.service.WordSearchService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class SearchController {

    private final WordSearchService service;

    public SearchController(WordSearchService service) {
        this.service = service;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }

    @PostMapping("/search/file")
    public SearchResponse searchFile(@RequestBody SearchFileRequest req) {
        return service.searchInFile(req.lang(), req.nbCar(), req.lstCar(), req.lstHint(), req.strict());
    }

    @PostMapping("/search/many")
    public SearchResponse searchMany(@RequestBody SearchManyRequest req) {
        return service.searchInManyFiles(req.lang(), req.cars(), req.lstHint());
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ProblemDetail handleBadRequest(IllegalArgumentException e) {
        // RFC 9457 problem+json (replaces the ad-hoc {"error": ...} body)
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, e.getMessage());
    }
}
