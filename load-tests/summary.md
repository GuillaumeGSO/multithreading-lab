# Load test summary

Generated 2026-11-23 by `compare.py` from 3 round(s). Latencies in ms (lower is better); with several rounds the value is the median across rounds and the parentheses give the min–max range. Every service ran the same `artillery.yml` at the same constant arrival rate.

## `SEARCH_MODE=baseline`

| Language | /search/file p50 | /search/file p95 | /search/many p50 | /search/many p95 | failures |
|---|---:|---:|---:|---:|---:|
| Python | 252.2 (82.3–6187.2) | 2780.0 (1556.5–27181.5) | 699.4 (320.6–9801.2) | 4867.0 (2465.6–28862.3) | 868 |
| Java | 5.0 (5.0–7.0) | 46.1 (13.9–507.8) | 7.9 (7.0–10.9) | 64.7 (16.9–507.8) | 0 |
| Go | 3.0 (3.0–4.0) | 6.0 (6.0–125.2) | 5.0 (4.0–7.0) | 13.1 (10.1–186.8) | 0 |
| Node/NestJS | 4.0 (4.0–4.0) | 10.9 (7.0–15.0) | 8.9 (7.9–8.9) | 24.8 (16.9–36.2) | 0 |
| C# | 4.0 (3.0–4.0) | 6.0 (6.0–7.9) | 8.9 (7.0–10.1) | 19.9 (18.0–23.8) | 0 |

## `SEARCH_MODE=parallel`

| Language | /search/file p50 | /search/file p95 | /search/many p50 | /search/many p95 | failures |
|---|---:|---:|---:|---:|---:|
| Python | 4492.8 (685.5–5378.9) | 24107.7 (23162.4–26115.6) | 7709.8 (1300.1–8868.4) | 26115.6 (17859.2–28290.8) | 1160 |
| Java | 5.0 (5.0–6.0) | 13.1 (10.9–1556.5) | 7.0 (7.0–7.9) | 16.9 (16.9–2369.0) | 0 |
| Go | 3.0 (3.0–3.0) | 5.0 (5.0–10.1) | 4.0 (4.0–4.0) | 7.9 (7.0–21.1) | 0 |
| Node/NestJS | 3.0 (3.0–4.0) | 7.0 (6.0–10.9) | 7.0 (7.0–7.0) | 16.9 (16.0–21.1) | 0 |
| C# | 4.0 (3.0–4.0) | 6.0 (6.0–10.1) | 6.0 (5.0–6.0) | 10.9 (10.9–16.9) | 0 |
