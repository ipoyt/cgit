"""cgit — a git wrapper where Claude writes the commit message and keeps docs in sync.

    cgit commit [-a] [-y] [--no-docs]   AI commit message -> code commit -> docs commit
    cgit docs [REV]                     sync docs with an existing commit (default HEAD)
    cgit knowledge [--rebuild]          show / rebuild the compressed code-base knowledge
    cgit <anything else>                passed straight to git

Claude is driven through the Claude Code CLI in headless mode (`claude -p`), so it
uses whatever login/auth Claude Code already has. No Python dependencies.
"""
