# cgit

A `git` wrapper where Claude writes your commit messages and keeps the repo's
documentation in step with the code, one commit at a time instead of a batch
update once a month.

```
$ cgit commit
› Writing commit message
┌──────────────────────────────────────────────────┐
│ Add --shout flag and GREET_WORD env var to greet │
│ ...                                              │
└──────────────────────────────────────────────────┘
[y] commit  [e] ask Claude to change it  [m] edit manually  [n] abort: e
What should change? › use a feat: prefix
...
[main e04c747] feat: add --shout flag and GREET_WORD env var
› Updating documentation
 README.md | 12 ++++++++++--
› docs: documented --shout and GREET_WORD in README usage/config
[main b660130] docs: sync documentation with e04c747
```

## What `cgit commit` does

1. Stages your changes. It uses what is already staged; `-a` stages modified
   tracked files; if nothing is staged it offers `git add -A`.
2. Loads the **compressed knowledge** of the code base (see below), so Claude
   understands the diff without re-reading the repo.
3. Claude writes a commit message from the staged diff, matching the style
   of your recent commits and branch name.
4. You review it: **y** commits, **e** sends Claude an instruction for what to
   change, **m** opens your git editor, **n** aborts (changes stay staged).
5. It makes the **code commit**, with your git hooks running as usual.
6. The docs agent reads the commit and edits only the documentation files
   (`*.md`, `*.rst`, `docs/*`, ... configurable) that the change made stale.
   - Any non-doc file it touches is reverted.
   - Docs that you have uncommitted edits in are left alone.
7. It makes the **docs commit**, with a standard message
   (`docs: sync documentation with <sha>`). If nothing needed changing, no
   docs commit is made.
8. It refreshes the knowledge base in the background from the new diff.

## Commands

| Command | |
|---|---|
| `cgit commit [-a] [-y] [--no-docs]` | Full flow above. `-y` accepts the message without asking. |
| `cgit docs [REV]` | Run only the docs sync for an existing commit (default `HEAD`). |
| `cgit knowledge` | Print the stored knowledge, updating it first if it is stale. |
| `cgit knowledge --rebuild` / `cgit init` | Re-explore the repo from scratch. |
| `cgit knowledge --path` | Show where the knowledge is stored. |
| anything else | Passed straight to `git`. `cgit commit -m "..."` (any flag cgit doesn't own) is plain `git commit`. |

## Compressed knowledge

- **First run:** an agent explores the repo with read-only tools and writes a
  dense markdown summary (~1500 words). It covers purpose, layout, key
  components, data flow, conventions and a *documentation map* (which doc
  covers what). This is stored per clone at `.git/cgit/knowledge.md`, so it is
  never committed. Set `knowledge_dir` in `.cgit.toml` to store it elsewhere.
- **Later runs:** the summary records the commit it describes. When `HEAD`
  moves (through cgit or plain git), only `git diff <base> HEAD` is sent to
  update it. The repo is never re-read. If the base commit disappears, for
  example after a rebase and gc, the summary is rebuilt from scratch.

## Install

On Linux, macOS and Windows, install it as a Python tool with
[uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/):

```sh
uv tool install /path/to/cgit        # or: pipx install /path/to/cgit
uv tool install -e /path/to/cgit     # editable: edits to the checkout apply at once
uv tool upgrade cgit                 # after pulling changes (non-editable install)
uv tool uninstall cgit
```

This puts a `cgit` command (`cgit.exe` on Windows) on `PATH`. If `PATH`
doesn't include it yet, `uv tool update-shell` adds it. uv also downloads a
suitable Python if yours is too old.

On Linux and macOS you can instead run `./install.sh`, which symlinks the
`cgit` launcher from this checkout into `~/.local/bin`. The launcher is thin:
the code lives in `cgit_lib/` next to it, so keep the two together.

Requirements:

- Python ≥ 3.11 (standard library only).
- `git`. cgit uses `$CGIT_GIT_BIN` if it is set, otherwise the first `git` on
  `PATH` that isn't cgit itself. So you can also install cgit under the name
  `git` (`ln -s …/cgit ~/.local/bin/git`) and every git command still reaches
  the real git.
- Claude Code, already logged in.

cgit runs Claude through the Claude Code CLI in headless mode (`claude -p`), so
it needs no API key of its own. It looks for the binary in this order:

1. `$CGIT_CLAUDE_BIN`
2. `claude` on `PATH`
3. The binary bundled with the VS Code extension
   (`~/.vscode-server/extensions/anthropic.claude-code-*/…`, or
   `%USERPROFILE%\.vscode\extensions\…` on Windows)

On Windows, cgit runs your git editor (for **m** in the commit review) through
the `sh.exe` that ships with Git for Windows, just as git does.

## Per-repo configuration

Copy [`cgit.example.toml`](cgit.example.toml) to `.cgit.toml` in a repo's root.
You can set:

- Models.
- Which doc globs are editable or excluded.
- The docs commit message template.
- `review_docs = true`, to see and approve the docs diff before it is committed.
- Extra commit-message rules, such as ticket prefixes.
- `knowledge_dir`, to move the knowledge and refresh state out of `.git/cgit`.
  The path is relative to the repo root or absolute. A folder inside the repo
  gets its own `.gitignore` so it is never committed. Give each repo its own
  folder, because two repos sharing one would overwrite each other's knowledge.

## Costs and limits

Each `cgit commit` makes 2–3 Claude calls (message, docs, background
knowledge refresh), plus one more for each "e" revision. Diffs larger than
`max_diff_chars` are truncated. The docs agent can still open files itself,
but the commit message only sees the diff stat for the truncated part.
