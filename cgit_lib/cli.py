import argparse
import os
import sys

from .commit import edit_in_editor, generate_message, git_commit, message_context, print_message
from .docs import sync_docs
from .knowledge import background_refresh_entry, build_knowledge, ensure_knowledge, refresh_knowledge_in_background
from .repo import Repo
from .util import ask, die, git, git_bin


def commit_parser():
    p = argparse.ArgumentParser(prog="cgit commit", description="Commit with a Claude-written message, then sync docs.")
    p.add_argument("-a", "--all", action="store_true", help="stage modified tracked files first (like git commit -a)")
    p.add_argument("-y", "--yes", action="store_true", help="accept the generated message without asking")
    p.add_argument("--no-docs", action="store_true", help="skip the documentation sync")
    return p


def docs_parser():
    p = argparse.ArgumentParser(prog="cgit docs", description="Sync documentation with a commit.")
    p.add_argument("rev", nargs="?", default="HEAD", help="commit to sync the docs with (default: HEAD)")
    return p


def knowledge_parser():
    p = argparse.ArgumentParser(prog="cgit knowledge", description="Show or rebuild the stored code-base knowledge.")
    p.add_argument("--rebuild", action="store_true", help="re-explore the repository from scratch")
    p.add_argument("--path", action="store_true", help="print where the knowledge is stored")
    return p


def print_help():
    out = ["cgit: git, with Claude writing your commit messages and keeping docs in sync.", "", "Commands:"]
    for p in (commit_parser(), docs_parser(), knowledge_parser()):
        out += [f"  {p.format_usage().removeprefix('usage: ').replace('[-h] ', '').strip()}", f"      {p.description}"]
        for a in p._actions:
            if isinstance(a, argparse._HelpAction):
                continue
            name = ", ".join(a.option_strings) or a.dest
            out.append(f"      {name:<14}{a.help}")
        out.append("")
    out += [
        "  cgit init",
        "      Same as `cgit knowledge --rebuild`.",
        "",
        "  cgit help, cgit -h, cgit --help, cgit",
        "      Show this help. Add -h to any command for just its options.",
        "",
        "Anything else goes straight to git: `cgit push`, `cgit log`, `cgit commit -m ...`.",
        "Use `git help` or `cgit help <command>` for git's own help.",
        "",
        "Environment:",
        "  CGIT_CLAUDE_BIN  path to the `claude` binary (default: PATH, then the VS Code extension's copy)",
        "  CGIT_GIT_BIN     path to the real `git` (default: first `git` on PATH that isn't cgit)",
        "",
        "Configuration: .cgit.toml in the repository root (see cgit.example.toml).",
    ]
    print("\n".join(out))


def cmd_commit(argv):
    args = commit_parser().parse_args(argv)

    repo = Repo()
    if args.all:
        git("add", "-u")
    if not git("diff", "--cached", "--name-only").strip():
        if not git("status", "--porcelain").strip():
            die("nothing to commit, working tree clean", code=0)
        if args.yes or ask("Nothing staged. Stage all changes (git add -A)? [Y/n] ", {"y", "n"}, default="y") == "y":
            git("add", "-A")
        else:
            die("nothing staged")

    knowledge = ensure_knowledge(repo)
    context = message_context(repo, knowledge)
    message = generate_message(repo, context)

    while not args.yes:
        print_message(message)
        choice = ask("\n[y] commit  [e] ask Claude to change it  [m] edit manually  [n] abort: ",
                     {"y", "e", "m", "n"})
        if choice == "y":
            break
        if choice == "n":
            die("aborted; your changes are still staged", code=1)
        if choice == "m":
            message = edit_in_editor(message) or message
        if choice == "e":
            try:
                feedback = input("What should change? › ").strip()
            except EOFError:
                feedback = ""
            if feedback:
                message = generate_message(repo, context, previous=message, feedback=feedback)

    if not git_commit(message):
        die("commit failed (see git output above); nothing was changed")

    if not args.no_docs:
        sync_docs(repo, "HEAD", knowledge)
    refresh_knowledge_in_background(repo)


def cmd_docs(argv):
    """Sync / update documentation with a commit."""
    args = docs_parser().parse_args(argv)
    repo = Repo()
    sync_docs(repo, args.rev, ensure_knowledge(repo))
    refresh_knowledge_in_background(repo)


def cmd_knowledge(argv):
    """Show or rebuild the stored code-base knowledge."""
    args = knowledge_parser().parse_args(argv)
    repo = Repo()
    if args.path:
        print(repo.path("knowledge.md"))
        return
    text = build_knowledge(repo) if args.rebuild else ensure_knowledge(repo)
    print(text)


def main():
    argv = sys.argv[1:]
    commands = {"commit": cmd_commit, "docs": cmd_docs, "knowledge": cmd_knowledge,
                "init": lambda a: cmd_knowledge(["--rebuild", *a])}
    if argv in ([], ["-h"], ["--help"], ["help"]):
        return print_help()
    if argv and argv[0] == "__refresh-knowledge":
        return background_refresh_entry()
    if argv and argv[0] in commands:
        # `cgit commit -m "..."` and other plain-git flags fall through to git itself.
        known = {"-a", "--all", "-y", "--yes", "--no-docs", "-h", "--help"}
        if argv[0] != "commit" or all(a in known for a in argv[1:]):
            return commands[argv[0]](argv[1:])
    os.execv(git_bin(), ["git", *argv])


def run():
    try:
        main()
    except KeyboardInterrupt:
        die("interrupted", code=130)
