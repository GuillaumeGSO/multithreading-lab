package com.lab.search.service;

/// Positional constraint on a word, as used by the search algorithm.
/// `position` is 1-indexed; a null or empty `letter` imposes no constraint;
/// when `excluded` is true the letter must NOT appear at `position`.
public record Hint(int position, String letter, boolean excluded) {
}
