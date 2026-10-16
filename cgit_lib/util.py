import fnmatch
import functools
import os
import shutil
import subprocess
import sys
import threading
import time

# The `cgit` launcher next to this package.
LAUNCHER = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "cgit")


def die(msg, code=1):
    print(f"cgit: {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg):
    print(f"\033[36m›\033[0m {msg}", file=sys.stderr)


def warn(msg):
    print(f"\033[33m! {msg}\033[0m", file=sys.stderr)


def setup_console():
    """Windows: turn on ANSI colours in the console and never crash on unencodable output."""
    if os.name != "nt":
        return
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    for std in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
        handle = ctypes.c_void_p(kernel32.GetStdHandle(std))
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    for stream in (sys.stdout, sys.stderr):
        if stream:
            stream.reconfigure(errors="replace")


@functools.cache
def git_bin():
    explicit = os.environ.get("CGIT_GIT_BIN")
    if explicit:
        return shutil.which(explicit) or die(f"CGIT_GIT_BIN={explicit} is not an executable")
    names = ["git"]
    if os.name == "nt":
        names = ["git" + ext.lower() for ext in os.environ.get("PATHEXT", ".EXE").split(os.pathsep) if ext]
    # Skip cgit itself, so it can be installed under the name `git`.
    self_paths = {os.path.normcase(p) for p in (LAUNCHER, os.path.realpath(sys.argv[0]))}
    for d in os.environ.get("PATH", "").split(os.pathsep):
        for name in names:
            p = os.path.join(d or ".", name)
            if (os.path.isfile(p) and os.access(p, os.X_OK)
                    and os.path.normcase(os.path.realpath(p)) not in self_paths):
                return p
    die("git not found on PATH. Install it or set CGIT_GIT_BIN to the real `git` binary.")


@functools.cache
def sh_bin():
    """A POSIX shell for running git's editor command; on Windows, the one shipped with Git for Windows."""
    if os.name != "nt":
        return "/bin/sh"
    # git.exe lives in Git\cmd, Git\bin or Git\mingw64\bin; sh.exe in Git\bin or Git\usr\bin.
    git_dir = os.path.dirname(os.path.realpath(git_bin()))
    for top in (os.path.dirname(git_dir), os.path.dirname(os.path.dirname(git_dir))):
        for rel in ("bin", os.path.join("usr", "bin")):
            p = os.path.join(top, rel, "sh.exe")
            if os.path.isfile(p):
                return p
    return shutil.which("sh") or die("sh not found; it ships with Git for Windows and is needed to run your git editor")


def git(*args, check=True, input=None):
    r = subprocess.run([git_bin(), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", input=input)
    if check and r.returncode != 0:
        die(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def clip(text, limit):
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[... truncated {len(text) - limit} more characters ...]\n"


def strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def ask(prompt, choices, default=None):
    while True:
        try:
            ans = input(prompt).strip().lower()
        except EOFError:
            ans = ""
        if not ans and default:
            return default
        if ans in choices:
            return ans


def matches(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


class Spinner:
    def __init__(self, text):
        self.text = text
        self._stop = threading.Event()
        self._thread = None

    def _spin(self):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        start, i = time.time(), 0
        while not self._stop.wait(0.1):
            sys.stderr.write(f"\r\033[35m{frames[i % len(frames)]}\033[0m {self.text} ({int(time.time() - start)}s)")
            sys.stderr.flush()
            i += 1

    def __enter__(self):
        if sys.stderr.isatty():
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            info(self.text)
        return self

    def __exit__(self, *exc):
        if self._thread:
            self._stop.set()
            self._thread.join()
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()
