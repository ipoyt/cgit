import os
import subprocess
import sys

from .claude import claude
from .commit import git_commit
from .knowledge import load_knowledge
from .prompts import DOCS_SYSTEM
from .util import ask, clip, die, git, git_bin, info, warn


def sync_docs(repo, rev="HEAD", knowledge=None):
    sha = git("rev-parse", rev).strip()
    short_sha = sha[:7]
    subject = git("log", "-1", "--format=%s", sha).strip()
    message = git("log", "-1", "--format=%B", sha).strip()

    before = repo.dirty_snapshot()
    docs = repo.doc_files()
    locked = [d for d in docs if d in before]  # dev has uncommitted edits there
    editable = [d for d in docs if d not in before]
    if not editable:
        info("no editable documentation files found — skipping docs sync")
        return
    if locked:
        warn(f"skipping docs with uncommitted changes: {', '.join(locked)}")

    stat = git("show", "--stat", "--format=", sha)
    diff = git("show", "--format=", "--find-renames", sha)
    if knowledge is None:
        knowledge, _ = load_knowledge(repo)
    prompt = (
        f"## Commit {short_sha}\n{message}\n\n## Diff stat\n{stat}\n"
        f"## Diff\n{clip(diff, repo.cfg['max_diff_chars'])}\n\n"
        + (f"## Code-base knowledge\n{knowledge}\n\n" if knowledge else "")
        + "## Editable documentation files\n" + "\n".join(f"- {d}" for d in editable)
        + "\n\nUpdate the documentation for this commit now."
    )
    reply = claude(prompt, system=DOCS_SYSTEM, model=repo.cfg["docs_model"],
                   tools=["Read", "Glob", "Grep", "Edit"], timeout=1200,
                   label="Updating documentation")
    summary = next((l.split(":", 1)[1].strip() for l in reversed(reply.splitlines())
                    if l.strip().startswith("SUMMARY:")), "")

    after = repo.dirty_snapshot()
    changed = [p for p, h in after.items() if before.get(p, "missing") != h]
    doc_changes = [p for p in changed if p in editable]
    stray = [p for p in changed if p not in editable]
    for p in stray:
        if p in before:
            warn(f"docs agent touched {p}, which already had uncommitted changes — check it manually")
        elif git("ls-files", "--error-unmatch", p, check=False):
            git("checkout", "--", p)
            warn(f"reverted non-doc change by docs agent: {p}")
        else:
            os.remove(p)
            warn(f"removed file created by docs agent: {p}")

    if not doc_changes:
        info("docs are already up to date")
        return

    print(git("diff", "--stat", "--", *doc_changes), file=sys.stderr, end="")
    info(f"docs: {summary or 'updated'}")
    if repo.cfg["review_docs"]:
        subprocess.run([git_bin(), "--no-pager", "diff", "--", *doc_changes])
        if ask("Commit these doc changes? [Y/n] ", {"y", "n"}, default="y") == "n":
            git("checkout", "--", *doc_changes)
            info("doc changes discarded")
            return

    fmt = {"sha": sha, "short_sha": short_sha, "subject": subject}
    msg = repo.cfg["docs_commit_message"].format(**fmt)
    body = repo.cfg["docs_commit_body"].format(**fmt)
    if body:
        msg += "\n\n" + body
    git("add", "--", *doc_changes)
    if not git_commit(msg, "--", *doc_changes):
        die("docs commit failed; doc edits are left staged")
