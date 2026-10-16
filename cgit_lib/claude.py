import glob
import json
import os
import shutil
import subprocess

from .util import Spinner, die

# Env vars set when running inside a Claude Code session; leaking them into the child
# `claude -p` makes it think it is a nested session.
_SESSION_ENV = (
    "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_EXECPATH", "CLAUDE_AGENT_SDK_VERSION", "CLAUDE_PID",
)


def claude_bin():
    explicit = os.environ.get("CGIT_CLAUDE_BIN")
    if explicit:
        return explicit
    found = shutil.which("claude")
    if found:
        return found
    # Fall back to the binary bundled with the VS Code extension (newest first).
    home = os.path.expanduser("~")
    candidates = []
    for ext_dir in (".vscode-server/extensions", ".vscode/extensions", ".cursor/extensions"):
        for name in ("claude", "claude.exe"):
            candidates += glob.glob(os.path.join(home, ext_dir, "anthropic.claude-code-*", "resources", "native-binary", name))
    candidates = [c for c in candidates if os.access(c, os.X_OK)]
    if candidates:
        return max(candidates, key=os.path.getmtime)
    die("Claude Code CLI not found. Install it or set CGIT_CLAUDE_BIN to the `claude` binary.")


def claude(prompt, *, system, model=None, tools=None, timeout=600, label="Claude is thinking"):
    """Run one headless Claude Code turn and return its final text.

    tools=None -> pure text completion with a replaced system prompt.
    tools=[...] -> agentic run with those tools; the cgit prompt is appended to
                   Claude Code's default system prompt so tool use stays competent.
    """
    cmd = [claude_bin(), "-p", "--output-format", "json", "--no-session-persistence"]
    if model:
        cmd += ["--model", model]
    if tools:
        tool_list = ",".join(tools)
        cmd += ["--tools", tool_list, "--allowedTools", tool_list,
                "--permission-mode", "acceptEdits", "--append-system-prompt", system]
    else:
        cmd += ["--tools", "", "--system-prompt", system]

    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV}
    with Spinner(label):
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            die(f"Claude timed out after {timeout}s")
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        die(f"unexpected output from claude (exit {r.returncode}):\n{(r.stderr or r.stdout).strip()[:2000]}")
    if data.get("is_error") or r.returncode != 0:
        die(f"claude failed: {data.get('result') or r.stderr.strip()}")
    return data.get("result", "")
