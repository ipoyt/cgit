import os
import subprocess
import sys
import time

from .claude import claude
from .prompts import KNOWLEDGE_BUILD_SYSTEM, KNOWLEDGE_UPDATE_SYSTEM
from .repo import Repo
from .util import LAUNCHER, clip, git, git_bin, info, strip_fences


def load_knowledge(repo):
    try:
        with open(repo.path("knowledge.md")) as f:
            text = f.read()
        with open(repo.path("knowledge.base")) as f:
            base = f.read().strip()
        return text, base
    except FileNotFoundError:
        return None, None


def save_knowledge(repo, text, base):
    for name, content in (("knowledge.md", text), ("knowledge.base", base or "")):
        tmp = repo.path(name + ".tmp")
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, repo.path(name))


def build_knowledge(repo):
    files = git("ls-files")
    prompt = (
        f"Repository root: {repo.root}\n\nTracked files:\n{clip(files, 40000)}\n\n"
        "Build the knowledge document now."
    )
    system = KNOWLEDGE_BUILD_SYSTEM.format(max_words=repo.cfg["knowledge_max_words"])
    text = strip_fences(claude(prompt, system=system, model=repo.cfg["knowledge_model"],
                               tools=["Read", "Glob", "Grep"], timeout=1800,
                               label="Building code-base knowledge (one-off)"))
    save_knowledge(repo, text, repo.head())
    return text


def refresh_knowledge(repo, quiet=False):
    """Bring the stored knowledge up to HEAD using only the diff since its base commit."""
    text, base = load_knowledge(repo)
    head = repo.head()
    if text is None:
        return build_knowledge(repo)
    if not head or base == head:
        return text
    r = subprocess.run([git_bin(), "cat-file", "-e", f"{base}^{{commit}}"], capture_output=True)
    if not base or r.returncode != 0:  # base was rewritten away (rebase/gc)
        return build_knowledge(repo)

    log = git("log", "--format=- %s", f"{base}..{head}")
    stat = git("diff", "--stat", base, head)
    diff = git("diff", base, head)
    prompt = (
        f"## Current knowledge document\n{text}\n\n"
        f"## Commits since it was written\n{log}\n## Diff stat\n{stat}\n"
        f"## Diff\n{clip(diff, repo.cfg['max_diff_chars'])}"
    )
    system = KNOWLEDGE_UPDATE_SYSTEM.format(max_words=repo.cfg["knowledge_max_words"])
    label = "Updating code-base knowledge"
    out = strip_fences(claude(prompt, system=system, model=repo.cfg["knowledge_model"], label=label))
    if out and out != "UNCHANGED":
        text = out
    save_knowledge(repo, text, head)
    return text


def ensure_knowledge(repo):
    lock = repo.path("refresh.lock")
    waited = 0
    while os.path.exists(lock) and _lock_alive(lock) and waited < 300:
        if waited == 0:
            info("waiting for background knowledge refresh to finish…")
        time.sleep(1)
        waited += 1
    return refresh_knowledge(repo)


def _lock_alive(lock):
    try:
        with open(lock) as f:
            os.kill(int(f.read().strip()), 0)
        return True
    except (ValueError, ProcessLookupError, FileNotFoundError, PermissionError):
        return False


def refresh_knowledge_in_background(repo):
    log = open(repo.path("refresh.log"), "w")
    proc = subprocess.Popen([sys.executable, LAUNCHER, "__refresh-knowledge"],
                            cwd=repo.root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    # Written by the parent so an immediate next `cgit commit` already sees it.
    with open(repo.path("refresh.lock"), "w") as f:
        f.write(str(proc.pid))


def background_refresh_entry():
    repo = Repo()
    try:
        refresh_knowledge(repo)
    finally:
        try:
            os.remove(repo.path("refresh.lock"))
        except FileNotFoundError:
            pass
