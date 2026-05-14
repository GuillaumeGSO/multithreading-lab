# Multithreading Lab

A personal learning project to experiment with multithreading across multiple languages using the **same logic and assets** in each implementation.

## Goal

Implement, then progressively optimize, identical concurrent programs in:

- **Python**
- **Java**
- **Go**
- **C++**

The intent is to observe and compare how each language expresses concurrency, what primitives it provides, and how performance characteristics differ — not to build something production-ready.

## Approach

Each language gets its own directory with a self-contained implementation of the same problem. The core logic and any shared assets (data files, configs, etc.) stay consistent across languages so that differences in code and performance are attributable to the language and its threading model, not the problem definition.

Each implementation will go through two phases:

1. **Baseline** — a straightforward multithreaded solution
2. **Optimized** — applying language-specific techniques (thread pools, lock-free structures, async runtimes, etc.)

## Structure

```
multithreading-lab/
├── python/
├── java/
├── go/
└── cpp/
```

## Languages & Threading Models

| Language | Primary concurrency model |
|----------|--------------------------|
| Python   | `threading`, `concurrent.futures`, GIL constraints |
| Java     | `Thread`, `ExecutorService`, `java.util.concurrent` |
| Go       | Goroutines + channels |
| C++      | `std::thread`, `std::mutex`, atomics |
