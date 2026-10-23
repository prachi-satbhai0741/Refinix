#!/usr/bin/env bash
#
# AegisForge — install the local git hooks.
#
# Every team member runs this ONCE per clone:
#
#   ./scripts/install-hooks.sh
#
# It points git at the version-controlled .githooks/ directory, so the
# pre-push guard (which blocks direct pushes to main and dev) is active and
# stays in sync with the repository.

set -euo pipefail

cd "$(dirname "$0")/.."

git rev-parse --git-dir >/dev/null 2>&1 || {
  echo "ERROR: not inside a git repository" >&2
  exit 1
}

existing="$(git config --get core.hooksPath || true)"
if [ -n "$existing" ] && [ "$existing" != ".githooks" ]; then
  echo "!! core.hooksPath is currently '$existing'; overwriting with '.githooks'" >&2
fi

git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true

echo "ok  hooks installed (core.hooksPath = .githooks)"
echo ""
echo "Active guard:"
echo "  pre-push  rejects direct pushes to 'main' and 'dev'"
echo ""
echo "Verify it works (this SHOULD fail):"
echo "  git push --dry-run origin HEAD:main"
echo ""
echo "To uninstall:  git config --unset core.hooksPath"
