# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A personal learning project implementing the same word-search logic across Python, Java, Go, and C++ to compare concurrency models and performance. Each language directory is self-contained. The `assets/` directory holds shared word lists (`assets/{lang}/{n}.txt`, where `n` is word length) used by all implementations.

## Structure

Each language gets its own directory (`python/`, `java/`, `go/`, `cpp/`). Each implementation goes through two phases:
1. **Baseline** — straightforward multithreaded solution
2. **Optimized** — language-specific techniques (thread pools, lock-free structures, async runtimes, etc.)

## Core Problem

The word search logic (see `python/seek_words.py`) filters words from dictionary files by:
- `nb_car`: word length (selects which asset file to open)
- `lst_car`: available letters (optional, with a `strict` mode that consumes letters)
- `lst_hint`: positional constraints (`Hint` objects with `pos`, `car`, `inverted`)

This logic must remain consistent across all language implementations.

## Python

No build step. Run directly with Python 3.

```bash
cd python
python seek_words.py
```

Dependencies: `unidecode`. Install with `pip install unidecode`.

## Concurrency Models by Language

| Language | Model |
|----------|-------|
| Python   | `threading`, `concurrent.futures` (GIL-constrained for CPU work) |
| Java     | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go       | Goroutines + channels |
| C++      | `std::thread`, `std::mutex`, atomics |
