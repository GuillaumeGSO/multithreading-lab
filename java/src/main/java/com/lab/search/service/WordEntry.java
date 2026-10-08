package com.lab.search.service;

/// One dictionary word with the data the scan needs, computed once when the word
/// list is loaded: the accent-free form (for the letter-pool check) and its a–z
/// letter counts (for strict mode). The per-query scan then allocates nothing.
public record WordEntry(String word, String normalized, byte[] freq) {

    public static WordEntry of(String word) {
        String normalized = WordSearchService.normalize(word);
        if (normalized.equals(word)) normalized = word; // share the string when accent-free
        byte[] freq = new byte[26];
        for (int i = 0; i < normalized.length(); i++) {
            int c = normalized.charAt(i) - 'a';
            if (c >= 0 && c < 26) freq[c]++;
        }
        return new WordEntry(word, normalized, freq);
    }
}
