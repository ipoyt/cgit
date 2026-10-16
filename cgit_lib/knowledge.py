import os
import subprocess
import sys
import time

from .claude import claude
from .prompts import KNOWLEDGE_BUILD_SYSTEM, KNOWLEDGE_UPDATE_SYSTEM
from .repo import Repo
from .util import clip, git, git_bin, info, strip_fences

# Directory holding cgit_lib, so `python -m cgit_lib` works from a checkout too.
_PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_knowledge(repo):
    try:
        with open(repo.path("knowledge.md"), encoding="utf-8") as f:
            text = f.read()
        with open(repo.path("knowledge.base"), encoding="utf-8") as f:
            base = f.read().strip()
        return text, base
    except FileNotFoundError:
        return None, None


def save_knowledge(repo, text, base):
    for name, content in (("knowledge.md", text), ("knowledge.base", base or "")):
        tmp = repo.path(name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
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
            pid = int(f.read().strip())
    except (ValueError, FileNotFoundError, PermissionError):
        return False
    return _pid_alive(pid)


def _pid_alive(pid):
    if os.name == "nt":
        # os.kill(pid, 0) would terminate the process on Windows, so ask the kernel instead.
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def refresh_knowledge_in_background(repo):
    log = open(repo.path("refresh.log"), "w")
    if os.name == "nt":
        # A hidden console of its own: survives the terminal closing, and `claude` opens no window.
        detach = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        detach = {"start_new_session": True}
    pythonpath = os.pathsep.join(p for p in (_PKG_PARENT, os.environ.get("PYTHONPATH")) if p)
    proc = subprocess.Popen([sys.executable, "-m", "cgit_lib", "__refresh-knowledge"],
                            cwd=repo.root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                            env=dict(os.environ, PYTHONPATH=pythonpath), **detach)
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
