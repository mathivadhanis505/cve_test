"""
trivy_runner.py

Runs Trivy against a repo filesystem and parses its JSON output into
normalized CVE records. Handles the modern Trivy schema (results live
under "Results", each with "Vulnerabilities" that may be null on a
clean scan).

Two entry points:
  - run_trivy_scan(repo_path)  -> shells out to the real `trivy` binary
  - parse_trivy_output(json_path_or_dict) -> pure parsing, used in tests
    so we never need a live Trivy install to validate logic.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scanner.ecosystem import TRIVY_TYPE_MAP


class TrivyExecutionError(RuntimeError):
    """Raised when the trivy CLI itself fails (not found, bad exit code, etc.)."""


@dataclass(frozen=True)
class CVERecord:
    vulnerability_id: str
    pkg_name: str
    installed_version: str
    fixed_version: str  # "" means no fix is available yet
    severity: str        # CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN
    title: str
    ecosystem: str        # npm | pip | maven | <raw trivy type if unmapped>
    target: str           # the manifest file path Trivy scanned, e.g. "package-lock.json"
    references: list[str]

    @property
    def has_fix(self) -> bool:
        return bool(self.fixed_version)


def run_trivy_scan(repo_path: str | Path, trivy_binary: str = "trivy") -> list[CVERecord]:
    """
    Shells out to a real Trivy install and scans repo_path as a filesystem target.
    Requires `trivy` to be on PATH. Pin the Trivy version in CI to keep scans
    reproducible — don't rely on whatever version happens to be installed.
    """
    cmd = [trivy_binary, "fs", "--format", "json", "--quiet", str(repo_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise TrivyExecutionError(
            f"'{trivy_binary}' not found on PATH. Install Trivy or pass trivy_binary=<path>."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise TrivyExecutionError(
            f"trivy exited with code {exc.returncode}. stderr: {exc.stderr}"
        ) from exc

    data = json.loads(result.stdout)
    return parse_trivy_output(data)


def parse_trivy_output(source: str | Path | dict) -> list[CVERecord]:
    """
    Parses Trivy's JSON output (modern schema, results under "Results") into
    a flat list of CVERecord. Accepts a dict already in memory, or a path to
    a JSON file (handy for fixture-driven testing).
    """
    if isinstance(source, dict):
        data = source
    else:
        data = json.loads(Path(source).read_text())

    records: list[CVERecord] = []

    for result in data.get("Results", []):
        target = result.get("Target", "")
        trivy_type = result.get("Type", "")
        ecosystem = TRIVY_TYPE_MAP.get(trivy_type, trivy_type)

        # Vulnerabilities is null on a clean scan of that target — guard with `or []`.
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
