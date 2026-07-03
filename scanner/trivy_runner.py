"""
trivy_runner.py

Runs Trivy against a repo filesystem and parses its JSON output into CVE records.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scanner.ecosystem import TRIVY_TYPE_MAP


class TrivyExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CVERecord:
    vulnerability_id: str
    pkg_name: str
    installed_version: str
    fixed_version: str
    severity: str
    title: str
    ecosystem: str
    target: str
    references: list[str]

    @property
    def has_fix(self) -> bool:
        return bool(self.fixed_version)


def run_trivy_scan(repo_path: str | Path, trivy_binary: str = "trivy") -> list[CVERecord]:
    cmd = [trivy_binary, "fs", "--format", "json", "--quiet", str(repo_path)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise TrivyExecutionError("Trivy not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise TrivyExecutionError(exc.stderr) from exc

    data = json.loads(result.stdout)
    return parse_trivy_output(data)


def parse_trivy_output(source: str | Path | dict) -> list[CVERecord]:
    if isinstance(source, dict):
        data = source
    else:
        data = json.loads(Path(source).read_text())

    records: list[CVERecord] = []

    for result in data.get("Results", []):
        target = result.get("Target", "")
        trivy_type = result.get("Type", "")
        ecosystem = TRIVY_TYPE_MAP.get(trivy_type, trivy_type)

        vulnerabilities = result.get("Vulnerabilities") or []

        for vuln in vulnerabilities:
            records.append(
                CVERecord(
                    vulnerability_id=vuln.get("VulnerabilityID", ""),
                    pkg_name=vuln.get("PkgName", ""),
                    installed_version=vuln.get("InstalledVersion", ""),
                    fixed_version=vuln.get("FixedVersion", "") or "",
                    severity=vuln.get("Severity", "UNKNOWN"),
                    title=vuln.get("Title", ""),
                    ecosystem=ecosystem,
                    target=target,
                    references=vuln.get("References", []) or [],
                )
            )

    return records


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)

    args = parser.parse_args()

    results = run_trivy_scan(args.repo)
    print(f"Found {len(results)} vulnerabilities")
