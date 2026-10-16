# Prerequisites

You need these before installing cgit:

- **Python 3.11 or newer.** cgit uses `tomllib`, which was added in 3.11. It
  needs nothing beyond the standard library.
- **git.** cgit uses `$CGIT_GIT_BIN` if set, otherwise the first `git` on
  `PATH` that isn't cgit itself.
- **Claude Code, installed and logged in.** cgit uses its login, so you don't
  need an API key. If `claude` isn't on your `PATH`, cgit also finds the copy
  bundled with the VS Code extension. You can also point `CGIT_CLAUDE_BIN` at
  the binary.

## Check

```sh
python3 --version   # 3.11 or newer
git --version
claude --version
```

## Getting Python

- Debian/Ubuntu/WSL: `sudo apt install python3`. Ubuntu 22.04 ships 3.10,
  which is too old, so install `python3.11` or newer there.
- macOS: `brew install python`
- No admin rights, or an old system Python: install
  [uv](https://docs.astral.sh/uv/) and run `uv python install 3.12`.
- Windows: `winget install astral-sh.uv`, then `uv tool install` cgit as
  shown in the README; uv fetches Python for you. Or install Python from
  python.org (the Microsoft Store `python` shortcut isn't a real Python).
  You also need [Git for Windows](https://git-scm.com/download/win).

On Windows, check with `py --version` (or `python --version`) instead of
`python3 --version`.
