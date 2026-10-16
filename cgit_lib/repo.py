import hashlib
import os
import tomllib

from .config import CONFIG_FILE, DEFAULT_CONFIG
from .util import die, git, matches


class Repo:
    def __init__(self):
        root = git("rev-parse", "--show-toplevel", check=False).strip()
        if not root:
            die("not inside a git repository")
        root = os.path.normpath(root)  # git prints C:/... on Windows; commonpath below needs C:\...
        os.chdir(root)
        self.root = root
        self.cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "rb") as f:
                self.cfg.update(tomllib.load(f))
        custom = self.cfg["knowledge_dir"]
        if custom:
            self.state_dir = os.path.abspath(os.path.expanduser(custom))
        else:
            self.state_dir = os.path.join(os.path.abspath(git("rev-parse", "--git-common-dir").strip()), "cgit")
        os.makedirs(self.state_dir, exist_ok=True)
        # Inside the work tree, keep it out of `git add -A` and the docs agent's change check.
        ignore = os.path.join(self.state_dir, ".gitignore")
        if custom and os.path.commonpath([self.state_dir, root]) == root and not os.path.exists(ignore):
            with open(ignore, "w") as f:
                f.write("*\n")

    def path(self, name):
        return os.path.join(self.state_dir, name)

    def head(self):
        return git("rev-parse", "--verify", "-q", "HEAD", check=False).strip() or None

    def doc_files(self):
        tracked = git("ls-files", "-z").split("\0")
        return [p for p in tracked if p and matches(p, self.cfg["docs"]) and not matches(p, self.cfg["docs_exclude"])]

    def dirty_snapshot(self):
        """{path: content hash or None if deleted} for every modified/untracked path."""
        out = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        entries, snap, i = out.split("\0"), {}, 0
        while i < len(entries):
            e = entries[i]
            i += 1
            if not e:
                continue
            status, p = e[:2], e[3:]
            if "R" in status or "C" in status:
                i += 1  # next entry is the rename source
            snap[p] = _file_hash(p)
        return snap


def _file_hash(p):
    try:
        with open(p, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()
    except (FileNotFoundError, IsADirectoryError):
        return None
