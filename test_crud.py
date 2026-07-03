from db.crud import (
    create_run,
    create_cve,
    create_patch,
    get_all_cves,
    get_all_patches,
    get_unpatched_cves,
    increment_repos_scanned,
    update_patch_status,
    finish_run
)

# Reset DB before running:
# python3 -m db.reset_db

run = create_run()
print("RUN CREATED:", run.id)

increment_repos_scanned(run.id)

cve1 = create_cve(
    repo="demo-pip",
    package="urllib3",
    severity="HIGH",
    installed_version="1.25",
    fixed_version="1.26",
    run_id=run.id
)

cve2 = create_cve(
    repo="demo-pip",
    package="requests",
    severity="MEDIUM",
    installed_version="2.20",
    fixed_version="2.31",
    run_id=run.id
)

print("CVE CREATED:", cve1.id)
print("CVE CREATED:", cve2.id)

print("\nUNPATCHED CVEs:")
for c in get_unpatched_cves(run.id):
    print(c.id, c.repo, c.package)

patch = create_patch(
    cve_id=cve1.id,
    run_id=run.id,
    branch_name="autopatch/CVE-TEST-001",
    pr_url="https://github.com/demo/pr/1",
    status="pending"
)

print("\nPATCH CREATED:", patch.id)

print("\nUNPATCHED CVEs:")
for c in get_unpatched_cves(run.id):
    print(c.id, c.repo, c.package)

print("\nALL CVES:")
for c in get_all_cves():
    print(c.id, c.repo, c.run_id, c.package)

print("\nALL PATCHES:")
for p in get_all_patches():
    print(p.id, p.cve_id, p.run_id, p.status)

update_patch_status(patch.id, "testing")
update_patch_status(patch.id, "merged")

final_run = finish_run(run.id)

print("\nFINAL RUN STATE:")
print("Repos scanned:", final_run.repos_scanned)
print("CVEs found:", len(get_all_cves()))
print("Patches opened:", final_run.patches_opened)
print("Patches merged:", final_run.patches_merged)

print("\nTRYING INVALID PATCH:")

try:
    other_run = create_run()

    create_patch(
        cve_id=cve2.id,
        run_id=other_run.id,
        branch_name="bad-branch",
        pr_url="https://github.com/demo/pr/2",
        status="pending"
    )

    print("ERROR: mismatch was allowed")

except ValueError as e:
    print("Correctly rejected:", e)
