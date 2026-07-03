import subprocess
import tempfile
from patcher.version_bumper import version_bump
import os
import requests

def branch_exists(repo, branch_name, token):
    response = requests.get(
        f"https://api.github.com/repos/{repo}/branches/{branch_name}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    return response.status_code == 200

def create_branch(x):
    token = os.environ["GITHUB_TOKEN"]
    work_dir = tempfile.mkdtemp()
    repo = x["repo"]     
    repo_url = f"https://{token}@github.com/{repo}"
    package = x["package"]
    fix_version = x["fix_version"] 
    cve_id = x["cve_id"]
    ecosystem = x["ecosystem"]

    result = subprocess.run(["git", "clone", repo_url, work_dir], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Clone failed for {repo}: {result.stderr}")
        return None
    
    branch_name = f"auto-patch/{cve_id}-{package}"
    if branch_exists(repo, branch_name, token):
        print(f"Branch already exists: {branch_name}, skipping")
        return None

    subprocess.run(["git", "checkout", "-b", branch_name], cwd=work_dir)
    
    result = version_bump(work_dir, package, fix_version, ecosystem)
    if(result):
        subprocess.run(["git", "add", "."], cwd=work_dir)
        subprocess.run(["git", "commit", "-m", f"fix(security): bump {package} to {fix_version} ({cve_id})"], cwd=work_dir)
        subprocess.run(["git", "push", "origin", branch_name], cwd = work_dir)
    else:
        return None
    print(f"Branch created: {branch_name}")
    return branch_name