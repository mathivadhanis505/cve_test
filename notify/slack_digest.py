import os
import requests

from db.crud import get_run_statistics, get_vulnerabilities
from db.models import Run, Patch
from db.session import get_session


def build_message():
    """
    Build a Slack summary for the latest scan run.
    """

    with get_session() as db:
        latest_run = (
            db.query(Run)
            .order_by(Run.id.desc())
            .first()
        )

        if latest_run is None:
            return "No scan has been executed yet."

        failed_patches = (
            db.query(Patch)
            .filter(
                Patch.run_id == latest_run.id,
                Patch.status == "failed"
            )
            .count()
        )

    stats = get_run_statistics(latest_run.id)
    vulnerabilities = get_vulnerabilities(latest_run.id)

    critical = sum(
        v.severity.upper() == "CRITICAL"
        for v in vulnerabilities
    )

    high = sum(
        v.severity.upper() == "HIGH"
        for v in vulnerabilities
    )

    return f"""
Nightly Dependency Report

Repositories Scanned     : {stats['repos_scanned']}
Critical Vulnerabilities : {critical}
High Vulnerabilities     : {high}
Patches Created          : {stats['patches_opened']}
Patches Merged           : {stats['patches_merged']}
Failed Patches           : {failed_patches}
"""


def send_slack_message(message):
    webhook = os.getenv("SLACK_WEBHOOK")

    if not webhook:
        print("SLACK_WEBHOOK not configured.")
        return

    response = requests.post(
        webhook,
        json={"text": message}
    )

    print(f"Slack response: {response.status_code}")

    if response.status_code != 200:
        print(response.text)


if __name__ == "__main__":
    message = build_message()
    print(message)
    send_slack_message(message)
