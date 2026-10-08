# In-process benchmark summary

Generated 2026-10-08 by `aggregate.py` from 3 round(s) per language. Each value is the geometric mean of the per-case medians, in ms (lower is better). With several rounds it shows the median across rounds and, in parentheses, the min–max range.

## `/search/file`

| Language | baseline | split |
|---|---:|---:|
| Python | 33.194 (33.126–34.314) | 42.525 (42.192–43.496) |
| Java | 0.535 (0.479–0.588) | 0.706 (0.665–0.783) |
| Go | 0.429 (0.400–0.477) | 0.399 (0.348–0.419) |
| Node/NestJS | 0.608 (0.593–0.713) | 0.965 (0.931–1.166) |
| C# | 0.496 (0.435–0.902) | 0.719 (0.667–0.741) |

## `/search/many`

| Language | baseline | fanout | nested |
|---|---:|---:|---:|
| Python | 115.933 (115.625–118.532) | 144.357 (144.277–152.574) | 157.556 (156.018–162.286) |
| Java | 2.000 (1.958–2.960) | 1.681 (1.659–2.053) | 1.970 (1.899–2.301) |
| Go | 1.445 (1.420–1.576) | 1.101 (1.019–1.205) | 1.010 (1.010–1.116) |
| Node/NestJS | 2.039 (1.954–2.224) | 2.432 (2.382–2.902) | 3.540 (3.331–3.831) |
| C# | 2.339 (2.327–2.450) | 2.031 (1.915–2.197) | 1.453 (1.440–1.582) |

## Scan vs positional index (`/search/file`)

Speedup of the index dispatcher over the single-threaded scan (geometric mean per query shape; above 1 means the index is faster).

| Shape | Python | Java | C# |
|---|---:|---:|---:|
| none | 1.0× | 0.8× | 1.2× |
| normal | 8.5× | 0.4× | 0.5× |
| excluded | 1.0× | 0.8× | 1.3× |
| mixed | 5.2× | 0.3× | 0.3× |
| none-wide | 1.0× | 1.0× | 1.1× |
| none strict | 1.0× | 0.9× | 1.0× |
| normal strict | 8.0× | 0.3× | 0.2× |
| excluded strict | 1.0× | 1.0× | 1.0× |
| mixed strict | 5.0× | 0.3× | 0.2× |
| normal nopool | 24.4× | 0.6× | 0.2× |
| mixed nopool | 19.2× | 0.4× | 0.2× |

## Throughput (many searches in flight, single-threaded scan each)

| Language | ops/sec |
|---|---:|
| Python | 3.8 (3.7–3.8) |
| Java | 269.9 (243.7–329.8) |
| Go | 822.0 (792.8–823.1) |
| Node/NestJS | 401.3 (331.0–407.5) |
| C# | 469.7 (404.5–645.3) |

## Correctness

All languages found the same number of words for every case.
