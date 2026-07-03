"""
cve_classifier.py

Takes the raw CVE list from trivy_runner.py and decides which ones are
actionable: i.e. which ones the patcher should actually open a PR for.

A CVE is actionable only if BOTH:
  1. Its severity is marked auto_patch: true in thresholds.yml
  2. Trivy reported a non-empty FixedVersion (no fix = nothing to patch to)

Everything else is returned separately as "informational" so it can still
be logged to the DB and show up in the Slack digest, without triggering
an auto-patch.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from scanner.trivy_runner import CVERecord

DEFAULT_THRESHOLDS_PATH = Path(__file__).resolve().parent.parent / "config" / "thresholds.yml"


@dataclass(frozen=True)
class ClassificationResult:
    actionable: list[CVERecord]      # auto_patch=true AND has a fix -> patcher should act
    informational: list[CVERecord]   # everything else -> log + alert only


def load_thresholds(path: str | Path = DEFAULT_THRESHOLDS_PATH) -> dict[str, bool]:
    """
    Loads thresholds.yml and returns a flat {severity: auto_patch_bool} map.
    Unknown severities (not listed in the file) default to False — fail safe,
    never auto-patch something we don't have an explicit rule for.
    """
    raw = yaml.safe_load(Path(path).read_text())
    severities = raw.get("severities", {})
    return {
        sev.upper(): bool(rule.get("auto_patch", False))
        for sev, rule in severities.items()
    }


def is_actionable(cve: CVERecord, thresholds: dict[str, bool]) -> bool:
    """A single CVE is actionable iff its severity auto-patches AND a fix exists."""
    if not cve.has_fix:
        return False
    return thresholds.get(cve.severity.upper(), False)


def classify(
    cves: list[CVERecord],
    thresholds: dict[str, bool] | None = None,
    thresholds_path: str | Path = DEFAULT_THRESHOLDS_PATH,
) -> ClassificationResult:
    """
    Main entry point. Splits a CVE list into actionable vs informational
    based on thresholds.yml (or a pre-loaded thresholds dict, useful for tests
    so you're not re-reading the YAML file every call).
    """
    if thresholds is None:
        thresholds = load_thresholds(thresholds_path)

    actionable: list[CVERecord] = []
    informational: list[CVERecord] = []

    for cve in cves:
        if is_actionable(cve, thresholds):
            actionable.append(cve)
        else:
            informational.append(cve)

    return ClassificationResult(actionable=actionable, informational=informational)
