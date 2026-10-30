"""Audit exact installed versions using a separately installed pinned pip-audit.

Run with the application Python after installing all service/persistence requirements.
Internal editable packages are verified individually and reviewed as source.
All other packages, including pip/test tooling, are included. No resolver or fix runs.
"""

import argparse
import importlib.metadata
import json
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from packaging.requirements import Requirement

INTERNAL_PACKAGES = {
    "classync-api-contracts": ("0.1.0", "api-contracts"),
    "classync-persistence": ("0.1.0", "persistence"),
}


def verify_local_source(distribution, root, directory):
    provenance = json.loads(distribution.read_text("direct_url.json") or "{}")
    url = urlparse(provenance.get("url", ""))
    if url.scheme != "file" or url.netloc or not provenance.get("dir_info", {}).get("editable"):
        raise ValueError("Internal package provenance is NOT VERIFIED")
    source = Path(url2pathname(unquote(url.path))).resolve()
    if source != (root / "packages" / directory).resolve():
        raise ValueError("Internal package source path is NOT VERIFIED")


def verify_local_contracts(distribution, root):
    verify_local_source(distribution, root, "api-contracts")


def inspect_report(report, expected):
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("Missing dependency results; scan is NOT VERIFIED")
    normalized = {d["name"].lower().replace("_", "-"): d for d in dependencies}
    if len(normalized) != len(dependencies) or set(normalized) != set(expected):
        raise ValueError("Incomplete scan coverage; scan is NOT VERIFIED")
    findings = set()
    for name, version in expected.items():
        dependency = normalized[name]
        if (
            dependency.get("skip_reason")
            or dependency.get("version") != version
            or not isinstance(dependency.get("vulns"), list)
        ):
            raise ValueError(f"Unverified dependency: {name}")
        for vulnerability in dependency.get("vulns", []):
            findings.add((name, vulnerability["id"]))
    return sorted(findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-python", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    installed = {
        d.metadata["Name"].lower().replace("_", "-"): d.version
        for d in importlib.metadata.distributions()
    }
    root = Path(__file__).resolve().parents[2]
    source_reviewed = {}
    for name, (version, directory) in INTERNAL_PACKAGES.items():
        if installed.pop(name, None) != version:
            raise ValueError(f"Expected local {name} installation is missing or changed")
        verify_local_source(importlib.metadata.distribution(name), root, directory)
        source_reviewed[name] = version
    verified_requirements = []
    for service in ("gateway", "academic", "scheduling", "notification", "persistence"):
        manifest = root / "services" / service / "requirements.txt"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith(("#", "-c", "-e")):
                continue
            requirement = Requirement(line)
            name = requirement.name.lower().replace("_", "-")
            if name not in installed or installed[name] not in requirement.specifier:
                raise ValueError(f"Installed version does not satisfy {service}: {name}")
        verified_requirements.append(str(manifest.relative_to(root)))
    requirements = output / "installed-third-party.txt"
    requirements.write_text(
        "".join(f"{name}=={version}\n" for name, version in sorted(installed.items())),
        encoding="utf-8",
    )
    (output / "scope.json").write_text(
        json.dumps(
            {
                "packages": installed,
                "service_manifests_verified": verified_requirements,
                "source_reviewed": source_reviewed,
            }
        ),
        encoding="utf-8",
    )
    version = subprocess.check_output(
        [args.tool_python, "-m", "pip_audit", "--version"], text=True, timeout=30
    ).strip()
    if version != "pip-audit 2.10.1":
        raise ValueError(f"Unexpected scanner version: {version}")
    report_path = output / "pip-audit.json"
    # Remove only this generated report, so a failed query cannot reuse stale success.
    report_path.unlink(missing_ok=True)
    result = subprocess.run(
        [
            args.tool_python,
            "-m",
            "pip_audit",
            "--no-deps",
            "--disable-pip",
            "-r",
            str(requirements),
            "--format",
            "json",
            "--output",
            str(report_path),
        ],
        check=False,
        timeout=300,
    )
    if result.returncode not in {0, 1} or not report_path.exists():
        raise RuntimeError("Scanner/network/tool failure: scan is NOT VERIFIED")
    findings = inspect_report(json.loads(report_path.read_text(encoding="utf-8")), installed)
    if bool(findings) != bool(result.returncode):
        raise ValueError("Scanner exit/result mismatch: scan is NOT VERIFIED")
    print(f"{version}: audited {len(installed)} exact versions; {len(findings)} distinct findings")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
