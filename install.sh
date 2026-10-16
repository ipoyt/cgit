#!/usr/bin/env sh
# Symlink cgit into ~/.local/bin (or $1).
set -e
here="$(cd "$(dirname "$0")" && pwd)"
dest="${1:-$HOME/.local/bin}"

# Prerequisites (see PREREQUISITES.md). Missing ones are reported, not fatal.
missing=0
if ! command -v python3 >/dev/null 2>&1; then
  echo "missing: python3 (3.11 or newer)"; missing=1
elif ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
  echo "missing: python3 3.11 or newer (found $(python3 --version 2>&1))"; missing=1
fi
if [ -n "$CGIT_GIT_BIN" ]; then
  [ -x "$CGIT_GIT_BIN" ] || command -v "$CGIT_GIT_BIN" >/dev/null 2>&1 \
    || { echo "missing: git (CGIT_GIT_BIN=$CGIT_GIT_BIN is not an executable)"; missing=1; }
elif ! command -v git >/dev/null 2>&1; then
  echo "missing: git"; missing=1
fi
# Same lookup order as cgit: $CGIT_CLAUDE_BIN, PATH, then the VS Code extension's copy.
claude_found=
if [ -n "$CGIT_CLAUDE_BIN" ]; then
  [ -x "$CGIT_CLAUDE_BIN" ] && claude_found=1
elif command -v claude >/dev/null 2>&1; then
  claude_found=1
else
  for c in "$HOME"/.vscode-server/extensions/anthropic.claude-code-*/resources/native-binary/claude \
           "$HOME"/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude \
           "$HOME"/.cursor/extensions/anthropic.claude-code-*/resources/native-binary/claude; do
    [ -x "$c" ] && claude_found=1 && break
  done
fi
if [ -z "$claude_found" ]; then
  echo "missing: Claude Code CLI (install it, or set CGIT_CLAUDE_BIN to the claude binary)"; missing=1
fi
if [ "$missing" = 1 ]; then
  echo "cgit will be installed, but won't work until the above is fixed. See $here/PREREQUISITES.md"
fi

mkdir -p "$dest"
chmod +x "$here/cgit"
ln -sf "$here/cgit" "$dest/cgit"
echo "installed: $dest/cgit -> $here/cgit"
case ":$PATH:" in
  *":$dest:"*) ;;
  *) echo "note: $dest is not on PATH; add this to ~/.bashrc:"
     echo "  export PATH=\"$dest:\$PATH\"" ;;
esac
