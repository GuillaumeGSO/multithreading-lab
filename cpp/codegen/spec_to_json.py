#!/usr/bin/env python3
"""Convert the API contract (openapi.yaml) to JSON for the /openapi.json endpoint.

Usage: spec_to_json.py <openapi.yaml> <openapi.json>
"""

import json
import sys

import yaml

with open(sys.argv[1], encoding="utf-8") as src, open(sys.argv[2], "w", encoding="utf-8") as dst:
    json.dump(yaml.safe_load(src), dst, ensure_ascii=False)
