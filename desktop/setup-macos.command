#!/bin/zsh
# Run once on the macOS coordinator after approving the setup in README.md.
set -euo pipefail
REFINIX_REPO="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$REFINIX_REPO"
REFINIX_PYTHON=/opt/homebrew/opt/python@3.12/bin/python3.12
"$REFINIX_PYTHON" -c 'import sys, platform; assert sys.platform == "darwin" and platform.machine() == "arm64" and sys.version_info[:2] == (3, 12), "This setup requires macOS arm64 and Python 3.12."'

print 'Refinix one-time setup: downloads 12.5 MB of pinned dependencies from PyPI.'
print 'Uses desktop/.venv; builds desktop/dist/Refinix.app. Reserve 1 GB for build output.'
print 'Does not install Ollama, download models, start Docker, or change the coordinator environment.'

"$REFINIX_PYTHON" -m venv desktop/.venv
REFINIX_ENV="$REFINIX_REPO/desktop/.venv/bin/python"
"$REFINIX_ENV" -m pip --isolated --disable-pip-version-check install \
  --index-url https://pypi.org/simple --only-binary=:all: --no-deps \
  --require-hashes -r desktop/requirements-build-macos.lock
"$REFINIX_ENV" -m pip --isolated --disable-pip-version-check download \
  --index-url https://pypi.org/simple --no-build-isolation --no-deps \
  --require-hashes -r desktop/requirements-macos.lock -d desktop/.packages
"$REFINIX_ENV" -m pip --isolated --disable-pip-version-check install \
  --no-index --find-links desktop/.packages --no-build-isolation \
  --require-hashes -r desktop/requirements-macos.lock
"$REFINIX_ENV" -m pip check
"$REFINIX_ENV" -c 'import sys; from AppKit import NSRunningApplication; sys.exit("Quit Refinix before rebuilding it.") if NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.refinix.desktop") else None'
print 'Building the app; detailed output is saved in desktop/build.log.'
# This directory contains only this script's generated build intermediates.
rm -rf -- "$REFINIX_REPO/desktop/build" "$REFINIX_REPO/desktop/dist/Refinix.app"
if ! "$REFINIX_ENV" desktop/setup_py2app.py py2app \
  --bdist-base "$REFINIX_REPO/desktop/build" --dist-dir "$REFINIX_REPO/desktop/dist" > desktop/build.log 2>&1; then
  tail -n 50 desktop/build.log
  exit 1
fi
/usr/bin/codesign --verify --deep --strict "$REFINIX_REPO/desktop/dist/Refinix.app"

print "Built: $REFINIX_REPO/desktop/dist/Refinix.app"
print 'Opening Refinix. After accepting the window, keep it in the Dock.'
open "$REFINIX_REPO/desktop/dist/Refinix.app"
