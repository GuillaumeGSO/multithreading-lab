"""HTTP-level tests: request validation at the API boundary.

Every request outside the contract's bounds (openapi.yaml) must be rejected with
HTTP 400 and an ErrorResponse body, never a 5xx, a crash, or a silent wrong result.
"""

import pytest
from fastapi.testclient import TestClient

from api import app
from common import Hint, load_base

client = TestClient(app)

PIN = {"position": 1, "letter": "a"}

# (path, body) pairs that violate the contract.
INVALID = [
    ("/search/file", {"wordLength": 5, "letters": ["a"], "hints": [{"position": 0, "letter": "a"}]}),
    ("/search/many", {"letters": "abc", "hints": [{"position": -1, "letter": "a"}]}),
    ("/search/file", {"wordLength": 5, "letters": ["a"], "hints": [{"position": 32, "letter": "a"}]}),
    ("/search/file", {"lang": "../../etc", "wordLength": 5, "letters": ["a"]}),
    ("/search/file", {"lang": "/etc", "wordLength": 5, "letters": ["a"]}),
    ("/search/many", {"lang": "xx", "letters": "abc"}),
    ("/search/file", {"wordLength": 0, "letters": ["a"]}),
    ("/search/file", {"wordLength": -1, "letters": ["a"]}),
    ("/search/file", {"wordLength": 32, "letters": ["a"]}),
    ("/search/file", {"letters": ["a"]}),
    ("/search/file", {"wordLength": 5, "letters": ["a"] * 33}),
    ("/search/file", {"wordLength": 5, "hints": [PIN] * 32}),
    ("/search/many", {"letters": "a" * 33}),
    ("/search/many", {"hints": [PIN]}),
    ("/search/many", {"letters": 123}),
    ("/search/file", {"wordLength": 5}),
]


@pytest.mark.parametrize("path,body", INVALID)
def test_invalid_request_is_400(path, body):
    res = client.post(path, json=body)
    assert res.status_code == 400, res.text
    assert isinstance(res.json()["error"], str)


@pytest.mark.parametrize("path", ["/search/file", "/search/many"])
def test_malformed_json_is_400(path):
    res = client.post(path, content=b"{not json", headers={"Content-Type": "application/json"})
    assert res.status_code == 400
    assert isinstance(res.json()["error"], str)


def test_valid_requests_at_the_bounds_are_200():
    res = client.post("/search/file", json={
        "lang": "fr", "wordLength": 5, "letters": list("elisa"),
        "hints": [{"position": 1, "letter": "s"}],
    })
    assert res.status_code == 200
    assert res.json()["count"] == len(res.json()["words"])
    assert client.post("/search/many", json={"lang": "en", "letters": "a" * 32}).status_code == 200


def test_core_rejects_unsafe_lang():
    for lang in ("../../etc", "/etc", "fr/../en", ""):
        with pytest.raises(ValueError):
            load_base(lang, 5)


def test_core_rejects_non_positive_hint_position():
    for position in (0, -1):
        with pytest.raises(ValueError):
            Hint(position, "a")
