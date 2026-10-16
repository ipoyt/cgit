DEFAULT_CONFIG = {
    "message_model": "sonnet",
    "docs_model": "sonnet",
    "knowledge_model": "sonnet",
    # Globs (fnmatch, `*` crosses `/`) of tracked files the docs agent may edit.
    "docs": ["*.md", "*.rst", "*.adoc", "docs/*", "doc/*"],
    "docs_exclude": ["CHANGELOG*", ".github/*"],
    "docs_commit_message": "docs: sync documentation with {short_sha}",
    "docs_commit_body": "Automatically updated by cgit to reflect {short_sha} ({subject}).",
    "review_docs": False,  # show the docs diff and ask before committing it
    "message_guidelines": "",  # extra rules appended to the commit-message prompt
    "max_diff_chars": 60000,
    "knowledge_max_words": 1500,
    # Where knowledge and refresh state live; relative to the repo root. Empty = .git/cgit.
    "knowledge_dir": "",
}

CONFIG_FILE = ".cgit.toml"
