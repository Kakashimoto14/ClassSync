"""Immutable review catalog. No automatic cohort allocation or code equivalence."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _catalog():
    return json.loads(
        (Path(__file__).parent / "catalogs/curriculum-review.json").read_text(encoding="utf-8")
    )


def catalog():
    # Return a copy; callers cannot mutate cached evidence.
    return json.loads(json.dumps(_catalog()))


def version(identity):
    return next((v.copy() for v in _catalog()["versions"] if v["id"] == identity), None)


def course(identity):
    return next((c.copy() for c in _catalog()["courses"] if c["id"] == identity), None)


PROGRAMS = {
    "BSIT": "bsit",
    "BSCPE": "bscpe",
    "BS ENTREP": "bse",
    "BSBA HRM": "bsba-hrm",
    "BECED": "beed-eced",
    "BEED GENERALIST": "beed-gen",
    "BSED SCIENCE": "bsed-sci",
    "BTLED ICT": "btled-ict",
}
