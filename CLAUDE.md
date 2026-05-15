# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A personal learning project implementing the same word-search logic across Python, Java, Go, and C++ to compare concurrency models and performance under HTTP load. Each language exposes the same REST API in its own Docker container. Artillery load tests (`load-tests/artillery.yml`) are container-agnostic — only `--target` changes per language.

## Core Problem

The word search logic filters words from dictionary files (`assets/{lang}/{n}.txt`, where `n` = word length) by available letters, positional hints, and word length. **This logic and the API contract must stay consistent across all language implementations.**

## API Contract (all languages)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/search/file` | Search words of fixed length |
| `POST` | `/search/many` | Search words across all lengths |

## Structure

```
multithreading-lab/
├── assets/             # Shared word lists
├── load-tests/
│   └── artillery.yml   # Container-agnostic load tests (change --target per language)
├── python/             # See python/README.md
├── docker-compose.yml  # Python=8000, Java=8001, Go=8002, C++=8003
└── CLAUDE.md
```

## Per-language READMEs

Each language directory has its own README covering local dev, Docker, and API details:
- [`python/README.md`](python/README.md)

## Concurrency Models by Language

| Language | Model |
|----------|-------|
| Python   | `threading`, `concurrent.futures` (GIL-constrained for CPU work) |
| Java     | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go       | Goroutines + channels |
| C++      | `std::thread`, `std::mutex`, atomics |
