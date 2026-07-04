import argparse

from db.crud import (
    get_unpatched_cves,
    create_patch,
)
from patcher.branch_creator import create_branch
from patcher.pr_manager import pr_open


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()

    cves = get_unpatched_cves(args.run_id)

    print(f"Found {len(cves)} unpatched vulnerabilities")

    for cve in cves:
        if not cve.fixed_version:
            print(f"Skipping {cve.package}: no fixed version available")
            continue

        data = {
            "repo": "mathivadhanis505/sample-vuln-python",
            "package": cve.package,
            "fix_version": cve.fixed_version.split(",")[0].strip(),
            "installed_version": cve.installed_version,
            "cve_id": f"CVE-{cve.id}",
            "ecosystem": "pip",
        }

        branch = create_branch(data)

        if not branch:
            continue

        pr_url = pr_open(data)

        create_patch(
            cve_id=cve.id,
            branch_name=branch,
            pr_url=pr_url,
            status="pending",
            run_id=args.run_id,
        )

        print(f"Created patch for {cve.package}")


if __name__ == "__main__":
    main()
