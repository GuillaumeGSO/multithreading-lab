# Load test summary

Generated 2026-10-08 by `compare.py` from 1 round(s). Latencies in ms (lower is better); with several rounds the value is the median across rounds and the parentheses give the min–max range. Every service ran the same `artillery.yml` at the same constant arrival rate.

## `SEARCH_MODE=baseline`

| Language | /search/file p50 | /search/file p95 | /search/many p50 | /search/many p95 | failures |
|---|---:|---:|---:|---:|---:|
| Python | 3395.5 | 8868.4 | 5168.0 | 12459.8 | 0 |
| Java | 8.9 | 36.2 | 10.9 | 74.4 | 0 |
| Go | 3.0 | 5.0 | 4.0 | 10.1 | 0 |
| Node/NestJS | 4.0 | 10.1 | 7.9 | 22.9 | 0 |
| C# | 3.0 | 8.9 | 7.0 | 19.9 | 0 |

## `SEARCH_MODE=parallel`

| Language | /search/file p50 | /search/file p95 | /search/many p50 | /search/many p95 | failures |
|---|---:|---:|---:|---:|---:|
| Python | 468.8 | 26643.2 | 1064.4 | 15218.6 | 600 |
| Java | 5.0 | 15.0 | 7.0 | 18.0 | 0 |
| Go | 3.0 | 6.0 | 4.0 | 8.9 | 0 |
| Node/NestJS | 4.0 | 18.0 | 7.9 | 22.9 | 0 |
| C# | 3.0 | 10.1 | 5.0 | 12.1 | 0 |
