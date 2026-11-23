from scripts.export_scheduling_contracts import check_contracts, render_contracts


def test_checked_in_scheduling_contracts_match_pydantic_sources():
    assert check_contracts() == []


def test_contract_check_reports_drift_without_rewriting_files(tmp_path):
    outputs = render_contracts()
    for relative_path, content in outputs.items():
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    (tmp_path / "packages/shared-types/src/scheduling.ts").write_text(
        "stale", encoding="utf-8"
    )
    before_schema = (tmp_path / "packages/api-contracts/schemas/scheduling-v1.json").read_text(
        encoding="utf-8"
    )

    drift = check_contracts(tmp_path)

    assert drift == ["packages/shared-types/src/scheduling.ts"]
    assert (tmp_path / "packages/shared-types/src/scheduling.ts").read_text(
        encoding="utf-8"
    ) == "stale"
    assert (tmp_path / "packages/api-contracts/schemas/scheduling-v1.json").read_text(
        encoding="utf-8"
    ) == before_schema
