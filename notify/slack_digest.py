import os
import requests


def build_message():
    """
    Temporary message.
    Later we'll fetch real numbers from the database.
    """
    return """
Nightly Dependency Report

Critical Vulnerabilities : 0
High Vulnerabilities     : 0
Patches Created          : 0
Failed Patches           : 0
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

    print(
        f"Slack response: "
        f"{response.status_code}"
    )


if __name__ == "__main__":
    message = build_message()
    print(message)

    # I will remove the comment later after Slack webhook is ready
    # send_slack_message(message) 