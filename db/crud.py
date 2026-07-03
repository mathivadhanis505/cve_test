from db.models import CVE, Patch, Run
from db.session import get_session
from sqlalchemy import update
from datetime import datetime


# -------------------
# RUN FUNCTIONS
# -------------------

def create_run():
    with get_session() as db:
        run = Run(
            started_at=datetime.utcnow(),
            repos_scanned=0,
            patches_opened=0,
            patches_merged=0
        )
        db.add(run)
        db.flush()      # gets run.id assigned without fully committing yet
        db.refresh(run)
        return run


# CHANGED: this is the most important fix in the whole file.
#
# THE PROBLEM (explained simply):
# Imagine a whiteboard showing the number 5. Two people walk up at almost
# the same moment:
#   - Person A reads "5", plans to write "6"
#   - Person B reads "5" too (before A writes anything), plans to write "6"
#   - Both write "6"
# But really it should be "7" -- two updates happened, only one stuck.
# One update silently vanished.
#
# Your old code did exactly this:
#   run.repos_scanned += repos_scanned_increment   <- read, then write
#
# If your scanner (Person 1) and your patcher (Person 3) both call this
# for the same run_id close together, one of their updates could get lost.
#
# THE FIX:
# Instead of "read the number in Python, then write a new number back,"
# tell the DATABASE to do the math itself, in one single atomic step:
# "add X to whatever is currently there" -- nothing can sneak in between
# the read and the write because there IS no separate read step anymore.
def update_run_stats(run_id, repos_scanned_increment=0, patches_opened_increment=0, patches_merged_increment=0):
    with get_session() as db:
        result = db.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                repos_scanned=Run.repos_scanned + repos_scanned_increment,
                patches_opened=Run.patches_opened + patches_opened_increment,
                patches_merged=Run.patches_merged + patches_merged_increment,
            )
        )

        if result.rowcount == 0:
            raise ValueError("Run not found")


def finish_run(run_id):
    with get_session() as db:
        run = db.query(Run).filter(Run.id == run_id).first()

        if not run:
            raise ValueError("Run not found")

        run.finished_at = datetime.utcnow()
        db.flush()
        db.refresh(run)
        return run


# NEW: a tiny helper so Person 1's scanner can record "I just finished
# checking one more repo" without misusing create_cve() to do it (see
# the repos_scanned bug below for why that matters).
def increment_repos_scanned(run_id, count=1):
    update_run_stats(run_id, repos_scanned_increment=count)


# -------------------
# CVE FUNCTIONS
# -------------------

# CHANGED: removed the "repos_scanned_increment=1" call that used to be
# inside this function.
#
# THE PROBLEM (explained simply):
# "repos_scanned" is supposed to mean "how many different repos we
# checked tonight." But this function used to add +1 to that number
# every time a SINGLE VULNERABILITY was found -- not once per repo.
#
# So if one repo had 5 vulnerabilities in it, the old code reported
# "5 repos scanned" when really it was 1 repo with 5 problems. That's
# like saying you visited 5 different stores when you actually visited
# 1 store and bought 5 things there.
#
# THE FIX:
# create_cve() no longer touches repos_scanned at all. Person 1's
# scanner should call increment_repos_scanned(run_id) exactly ONCE per
# repo it finishes checking, regardless of how many vulnerabilities
# that repo had (even zero).
def create_cve(
    repo,
    package,
    severity,
    installed_version,
    fixed_version,
    run_id
):
    if run_id is None:
        raise ValueError("run_id is required for CVE creation")

    with get_session() as db:
        cve = CVE(
            repo=repo,
            package=package,
            severity=severity,
            installed_version=installed_version,
            fixed_version=fixed_version,
            run_id=run_id
        )

        db.add(cve)
        db.flush()
        db.refresh(cve)
        return cve


def get_all_cves():
    with get_session() as db:
        return db.query(CVE).all()


# NEW: Person 3 (the patcher) needs this and shouldn't have to write
# their own database query just to find "what hasn't been fixed yet."
# This finds every CVE from a run that has no Patch row pointing at it.
def get_unpatched_cves(run_id):
    with get_session() as db:
        return (
            db.query(CVE)
            .outerjoin(Patch, Patch.cve_id == CVE.id)
            .filter(CVE.run_id == run_id, Patch.id.is_(None))
            .all()
        )


# -------------------
# PATCH FUNCTIONS
# -------------------

# CHANGED: added a check that cve.run_id matches the run_id you were
# given, before creating the patch.
#
# THE PROBLEM (explained simply):
# A Patch row stores TWO facts that should always agree: which CVE it
# fixes, and which run it belongs to. But the CVE row already knows
# which run IT belongs to. So you're storing the same fact in two
# places. If someone passes a cve_id from Run 5 but a run_id of Run 7
# by mistake, nothing used to stop that -- you'd end up with a Patch
# row that disagrees with itself about which run it's part of.
#
# THE FIX:
# Before saving, double-check the CVE's actual run_id matches what was
# passed in. If they disagree, refuse and raise a clear error instead
# of silently saving bad data.
def create_patch(
    cve_id,
    branch_name,
    pr_url,
    status,
    run_id
):
    if run_id is None:
        raise ValueError("run_id is required for Patch creation")

    with get_session() as db:
        cve = db.query(CVE).filter(CVE.id == cve_id).first()
        if not cve:
            raise ValueError("CVE not found")
        if cve.run_id != run_id:
            raise ValueError(
                f"run_id mismatch: CVE {cve_id} belongs to run "
                f"{cve.run_id}, not run {run_id}"
            )

        patch = Patch(
            cve_id=cve_id,
            run_id=run_id,
            branch_name=branch_name,
            pr_url=pr_url,
            status=status
        )

        db.add(patch)
        db.flush()
        db.refresh(patch)
        patch_id = patch.id

    # Runs as its own separate atomic update -- see update_run_stats above
    update_run_stats(run_id, patches_opened_increment=1)

    with get_session() as db:
        return db.query(Patch).filter(Patch.id == patch_id).first()


def get_all_patches():
    with get_session() as db:
        return db.query(Patch).all()


VALID_PATCH_STATUSES = {"pending", "testing", "merged", "failed"}


def update_patch_status(patch_id, new_status):
    if new_status not in VALID_PATCH_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    with get_session() as db:
        patch = db.query(Patch).filter(Patch.id == patch_id).first()

        if not patch:
            raise ValueError("Patch not found")

        old_status = patch.status
        patch.status = new_status
        db.flush()
        db.refresh(patch)
        run_id = patch.run_id
        result_patch_id = patch.id

    # Only count the transition INTO "merged" -- unchanged logic from
    # your original, just moved outside the session block so the atomic
    # update_run_stats call (which opens its own session) doesn't get
    # nested inside this one.
    if old_status != "merged" and new_status == "merged":
        update_run_stats(run_id, patches_merged_increment=1)

    with get_session() as db:
        return db.query(Patch).filter(Patch.id == result_patch_id).first()


def get_patch(patch_id):
    with get_session() as db:
        return db.query(Patch).filter(Patch.id == patch_id).first()



def get_run_statistics(run_id):
    with get_session() as db:

        run = (
            db.query(Run)
            .filter(Run.id == run_id)
            .first()
        )

        if not run:
            raise ValueError("Run not found")

        total_vulns = (
            db.query(CVE)
            .filter(CVE.run_id == run_id)
            .count()
        )

        total_patches = (
            db.query(Patch)
            .filter(Patch.run_id == run_id)
            .count()
        )

        merged_patches = (
            db.query(Patch)
            .filter(
                Patch.run_id == run_id,
                Patch.status == "merged"
            )
            .count()
        )

        return {
            "run_id": run.id,
            "repos_scanned": run.repos_scanned,
            "total_vulnerabilities": total_vulns,
            "patches_opened": total_patches,
            "patches_merged": merged_patches,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }




def get_vulnerabilities(run_id):
    with get_session() as db:
        return (
            db.query(CVE)
            .filter(CVE.run_id == run_id)
            .all()
        )
