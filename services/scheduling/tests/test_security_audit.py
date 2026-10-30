import json
from types import SimpleNamespace

import pytest

from scripts.security.python_audit import inspect_report, verify_local_contracts


@pytest.mark.parametrize(
    "editable,location", [(True, "local"), (False, "local"), (True, "remote"), (True, "elsewhere")]
)
def test_internal_package_requires_verified_local_editable_source(tmp_path, editable, location):
    expected = tmp_path / "packages" / "api-contracts"
    url = (
        expected.as_uri()
        if location == "local"
        else ("https://example.invalid/contracts" if location == "remote" else tmp_path.as_uri())
    )
    distribution = SimpleNamespace(
        read_text=lambda _: json.dumps({"url": url, "dir_info": {"editable": editable}})
    )
    if editable and location == "local":
        assert verify_local_contracts(distribution, tmp_path) is None
    else:
        with pytest.raises(ValueError):
            verify_local_contracts(distribution, tmp_path)


def test_clean_exact_coverage():
    assert (
        inspect_report(
            {"dependencies": [{"name": "pkg", "version": "1", "vulns": []}]}, {"pkg": "1"}
        )
        == []
    )


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"dependencies": []},
        {"dependencies": [{"name": "pkg", "version": "0", "vulns": []}]},
        {"dependencies": [{"name": "pkg", "version": "1", "skip_reason": "network"}]},
        {"dependencies": [{"name": "pkg", "version": "1"}]},
        {
            "dependencies": [
                {"name": "pkg", "version": "1", "vulns": []},
                {"name": "pkg", "version": "1", "vulns": []},
            ]
        },
    ],
)
def test_incomplete_or_skipped_scan_fails_closed(data):
    with pytest.raises(ValueError):
        inspect_report(data, {"pkg": "1"})


def test_duplicate_advisory_ids_are_not_double_counted():
    data = {
        "dependencies": [
            {
                "name": "pkg",
                "version": "1",
                "vulns": [
                    {"id": "A"},
                    {"id": "A"},
                    {"id": "B"},
                ],
            }
        ]
    }
    assert inspect_report(data, {"pkg": "1"}) == [("pkg", "A"), ("pkg", "B")]
