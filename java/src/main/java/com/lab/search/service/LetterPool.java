package com.lab.search.service;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/// A query's available letters, prepared once per search: a membership table for
/// the pool check and a–z counts for strict mode. Immutable, so one pool is
/// shared by every thread scanning the same query.
public final class LetterPool {

    private final boolean empty;
    private final boolean strict;
    private final boolean[] ascii = new boolean[128];
    private final Set<Character> other = new HashSet<>();
    private final int[] freq = new int[26];

    /// Each element of `letters` is one character; an element of several
    /// characters can never match a single letter.
    public LetterPool(List<String> letters, boolean strict) {
        this.strict = strict;
        boolean any = false;
        if (letters != null) {
            for (String l : letters) {
                if (l == null || l.length() != 1) continue;
                char c = l.charAt(0);
                any = true;
                if (c < 128) ascii[c] = true;
                else other.add(c);
                if (c >= 'a' && c <= 'z') freq[c - 'a']++;
            }
        }
        this.empty = !any;
    }

    /// Whether the word can be built from the pool: every letter of its
    /// accent-free form is in the pool, and in strict mode no a–z letter is
    /// needed more often than the pool holds it.
    public boolean matches(WordEntry e) {
        String n = e.normalized();
        if (n.isEmpty() || empty) return false;
        for (int i = 0; i < n.length(); i++) {
            char c = n.charAt(i);
            if (c < 128 ? !ascii[c] : !other.contains(c)) return false;
        }
        if (strict) {
            byte[] wf = e.freq();
            for (int i = 0; i < 26; i++) if (wf[i] > freq[i]) return false;
        }
        return true;
    }
}
