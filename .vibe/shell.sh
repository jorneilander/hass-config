#!/usr/bin/env bash
# Vibe shell wrapper: reproduce the direnv (.envrc) environment for every tool
# command, so the extension matches the terminal exactly.
# Wired up via `[tools.bash] shell` in .vibe/config.toml.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."

# Evaluate the repo's .envrc through direnv (cwd-scoped, so run it in a
# subshell to leave the command's own cwd untouched). direnv re-evaluates
# .envrc only when its hash changes; otherwise it replays the cached diff.
if command -v direnv >/dev/null 2>&1; then
    eval "$(cd "$REPO_ROOT" && direnv export bash 2>/dev/null)"
fi

# Fallback: if direnv is missing or the dir isn't allowed, activate the venv
# directly (this repo's .envrc only adds the venv to the environment).
if [ -z "$VIRTUAL_ENV" ] && [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
    source "$REPO_ROOT/.venv/bin/activate"
fi

exec /bin/bash "$@"
