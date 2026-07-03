import os
import requests

def pr_open(or_dict):
    repo = or_dict["repo"]
    package = or_dict["package"]
    cve_id = or_dict["cve_id"]
    or_version = or_dict["installed_version"]
    fix_version = or_dict["fix_version"]
    token = os.environ["GITHUB_TOKEN"]
    pr_title = f"Fixed vulnerability: {package} in {cve_id}"
    pr_body = f"Bump version of {package} from {or_version} to {fix_version}"

    git_response = requests.post(
        f"https://api.github.com/repos/{repo}/pulls",
        
        headers={
            "Authorization": f"Token {token}",
            "Accept": "application/vnd.github.v3+json"
        },

        json={
            "title": pr_title,
            "body": pr_body,
            "head": f"auto-patch/{cve_id}-{package}",
            "base": "main"
        }
    )
    response = git_response.json()
    if "html_url" not in response:
        print(f"PR failed for {package}: {response.get('message')}")
        return None
    return response["html_url"]