"""
ecosystem.py

Parses dependency manifest files across ecosystems (npm, pip, maven)
into one normalized shape:

    {"name": str, "version": str, "ecosystem": "npm" | "pip" | "maven"}

This is the shared contract every other module relies on. trivy_runner.py
doesn't need this for parsing scan results (Trivy already normalizes that),
but version_bumper.py (Person 3) and any manifest-reading code here will
both lean on these functions, so keep the return shape stable.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Dependency:
    name: str
    version: str
    ecosystem: str  # "npm" | "pip" | "maven"

    def as_dict(self) -> dict:
        return {"name": self.name, "version": self.version, "ecosystem": self.ecosystem}


# Maps Trivy's "Type" field (in scan results) to our ecosystem names.
# trivy_runner.py uses this to tag CVEs with the right ecosystem.
TRIVY_TYPE_MAP = {
    "npm": "npm",
    "pip": "pip",
    "pom": "maven",
}


def parse_npm(filepath: str | Path) -> list[Dependency]:
    """Parse package.json. Reads both dependencies and devDependencies."""
    path = Path(filepath)
    data = json.loads(path.read_text())

    deps: list[Dependency] = []
    for section in ("dependencies", "devDependencies"):
        for name, version in data.get(section, {}).items():
            # package.json versions often carry ^ or ~ prefixes; strip for comparison,
            # but version_bumper.py is responsible for preserving/rewriting the prefix
            # when it edits the file, so we keep the raw string here.
            deps.append(Dependency(name=name, version=version, ecosystem="npm"))
    return deps


def parse_pip(filepath: str | Path) -> list[Dependency]:
    """Parse requirements.txt. Handles ==, >=, ~= pins; skips comments/blank lines/-r includes."""
    path = Path(filepath)
    deps: list[Dependency] = []

    pin_pattern = re.compile(r"^([A-Za-z0-9_.\-\[\]]+)\s*(==|>=|~=|<=|!=)\s*([A-Za-z0-9.\-]+)")

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = pin_pattern.match(line)
        if not match:
            # Unpinned requirement (e.g. just "flask") — no version to track yet.
            continue
        name, _operator, version = match.groups()
        deps.append(Dependency(name=name, version=version, ecosystem="pip"))
    return deps


def parse_maven(filepath: str | Path) -> list[Dependency]:
    """Parse pom.xml. Reads <dependency> blocks under <dependencies>."""
    path = Path(filepath)
    tree = ET.parse(path)
    root = tree.getroot()

    # pom.xml uses a default namespace, which ElementTree requires explicitly.
    ns_match = re.match(r"\{(.*)\}", root.tag)
    ns = {"m": ns_match.group(1)} if ns_match else {}
    tag = lambda t: f"m:{t}" if ns else t

    deps: list[Dependency] = []
    for dep_el in root.findall(f".//{tag('dependencies')}/{tag('dependency')}", ns):
        group_id = dep_el.findtext(tag("groupId"), default="", namespaces=ns)
        artifact_id = dep_el.findtext(tag("artifactId"), default="", namespaces=ns)
        version = dep_el.findtext(tag("version"), default="", namespaces=ns)
        if not version:
            # Version managed elsewhere (e.g. parent POM / dependencyManagement) — skip.
            continue
        name = f"{group_id}:{artifact_id}"
        deps.append(Dependency(name=name, version=version, ecosystem="maven"))
    return deps


_PARSERS = {
    "npm": parse_npm,
    "pip": parse_pip,
    "maven": parse_maven,
}

_MANIFEST_FILENAMES = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pom.xml": "maven",
}


def detect_ecosystem(filepath: str | Path) -> str | None:
    """Guess ecosystem from filename. Returns None if unrecognized."""
    return _MANIFEST_FILENAMES.get(Path(filepath).name)


def parse_manifest(filepath: str | Path, ecosystem: str | None = None) -> list[Dependency]:
    """
    Main entry point. Parses a manifest file and returns normalized Dependency list.
    If ecosystem isn't given, it's inferred from the filename.
    """
    if ecosystem is None:
        ecosystem = detect_ecosystem(filepath)
        if ecosystem is None:
            raise ValueError(
                f"Can't infer ecosystem from filename '{Path(filepath).name}'. "
                f"Pass ecosystem explicitly: one of {list(_PARSERS)}."
            )

    parser = _PARSERS.get(ecosystem)
    if parser is None:
        raise ValueError(f"Unsupported ecosystem '{ecosystem}'. Must be one of {list(_PARSERS)}.")

    return parser(filepath)
