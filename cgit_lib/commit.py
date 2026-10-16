import os
import subprocess
import sys
import tempfile

from .claude import claude
from .prompts import MESSAGE_SYSTEM
from .util import clip, git, git_bin, sh_bin, strip_fences


def message_context(repo, knowledge):
    branch = git("branch", "--show-current", check=False).strip() or "(detached)"
    recent = git("log", "-15", "--format=- %s", check=False) or "(no commits yet)"
    stat = git("diff", "--cached", "--stat")
    diff = git("diff", "--cached", "--find-renames")
    guidelines = repo.cfg["message_guidelines"]
    return (
        f"## Code-base knowledge\n{knowledge}\n\n"
        f"## Branch\n{branch}\n\n## Recent commit subjects\n{recent}\n"
        + (f"## Extra guidelines\n{guidelines}\n\n" if guidelines else "")
        + f"## Staged diff stat\n{stat}\n## Staged diff\n{clip(diff, repo.cfg['max_diff_chars'])}"
    )


def generate_message(repo, context, previous=None, feedback=None):
    prompt = context
    if previous is not None:
        prompt += (
            f"\n\n## Your previous commit message\n{previous}\n\n"
            f"## Developer's requested change\n{feedback}\n\n"
            "Rewrite the commit message applying the developer's request. Output only the full message."
        )
    else:
        prompt += "\n\nWrite the commit message now."
    label = "Revising commit message" if previous else "Writing commit message"
    return strip_fences(claude(prompt, system=MESSAGE_SYSTEM, model=repo.cfg["message_model"], timeout=300, label=label))


def edit_in_editor(text):
    editor = git("var", "GIT_EDITOR").strip()
    with tempfile.NamedTemporaryFile("w+", suffix="COMMIT_EDITMSG", delete=False, encoding="utf-8") as f:
        f.write(text + "\n")
        path = f.name
    try:
        subprocess.run([sh_bin(), "-c", f'{editor} "$1"', editor, path])
        with open(path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if not l.startswith("#")]
        return "\n".join(lines).strip()
    finally:
        os.remove(path)


def print_message(msg):
    width = min(max((len(l) for l in msg.splitlines()), default=0), 100)
    bar = "─" * (width + 2)
    print(f"\n┌{bar}┐", file=sys.stderr)
    for l in msg.splitlines():
        print(f"│ \033[1m{l.ljust(width)}\033[0m │", file=sys.stderr)
    print(f"└{bar}┘", file=sys.stderr)


def git_commit(message, *extra):
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        f.write(message + "\n")
        path = f.name
    try:
        r = subprocess.run([git_bin(), "commit", "-F", path, *extra])  # hooks/output visible to the dev
    finally:
        os.remove(path)
    return r.returncode == 0
