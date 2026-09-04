# Refinix desktop shell

A native window around the coordinator that already exists in
[`backend/coordinator`](../backend/coordinator). It replaces nothing: the same
SQLite state, the same `/v1` routes, the same frontend, the same event stream.

| Path | What it is |
|---|---|
| [`lifecycle.py`](lifecycle.py) | startup and shutdown. No window toolkit, so it runs offline under test |
| [`shell.py`](shell.py) | the pywebview window, the startup screen and the native bridge |
| [`__main__.py`](__main__.py) | `python3 -m desktop`, with a `--no-window` mode |
| [`refinix.py`](refinix.py) | the script py2app launches inside `Refinix.app` |
| [`setup_py2app.py`](setup_py2app.py) | the macOS bundle build |
| [`requirements-macos.lock`](requirements-macos.lock) | exact macOS packages, sources, licences, sizes and SHA-256 hashes |
| [`setup-macos.command`](setup-macos.command) | one-time macOS install, build and open command |
| [`icons/`](icons/) | platform icons derived from the brand masters |

## Running it

The built macOS app is `desktop/dist/Refinix.app`. Double-click it in Finder,
then right-click its Dock icon → **Options → Keep in Dock**. No terminal or
external browser is needed for later launches. Source commands:

```bash
python3 -m desktop                 # native window (needs pywebview)
python3 -m desktop --no-window     # local services only; existing backend dependencies
python3 -m backend.coordinator     # unchanged; the desktop shell is optional
```

`--no-window` needs the existing backend dependencies, including Pydantic, and can
confirm the startup sequence on a machine where the toolkit is not installed.

## What opening Refinix does

1. Takes a per-user lock in `~/.aegisforge/desktop.lock`. A second launch does
   not start a second copy: it asks the running one to come forward and exits.
2. Chooses a loopback port. If the preferred port is busy, the occupant must
   answer as *this workspace's* coordinator before it is reused; anything else
   — another application, another workspace — is left alone and a different
   free port is taken.
3. Starts the coordinator in-process, bound to `127.0.0.1` only.
4. Detects Ollama. If it answers, it is used as-is. If it does not and the
   binary is installed, Refinix starts it and remembers that it owns it. If it
   is not installed, the window says so and gives the download page. **Nothing
   is downloaded or installed.**
5. Checks whether the configured model is installed and, if not, shows the
   exact `ollama pull` command. **No model is downloaded.**

Docker is never started. Ordinary Chat needs the model runtime, not a cluster,
and an offline Ubuntu worker does not block local Chat or cause a replacement
cluster to be created on the Mac.

Every step is bounded and every failure ends in a readable message with a
**Try again** button, so a failed start is never an endless loading screen.

## Quitting

Closing the window and Quit are the same path. If work is running, Refinix says
how much and asks; on confirmation it cancels those jobs through the same route
the Stop button uses, waits briefly for the cancellation to be recorded, and
then stops its own listener. A reused coordinator is queried and its active
requests are cancelled through loopback, while the existing coordinator process
stays running. Closing during startup cancels startup and releases late resources. It stops the model runtime **only if it started it** —
a runtime that was already running on the computer is left exactly as it was.

## The native bridge

The page can reach six methods and nothing else: `progress`, `retry_startup`,
`choose_files`, `open_state_folder`, `shell_info`, `quit`. None of them takes a
filesystem path, a URL or a command from the page. `choose_files` opens the
system picker, which a person has to act on, and reads the chosen bytes into
the coordinator itself; the page never sees a path. `open_state_folder` opens
one fixed directory and takes no argument. Model output rendered in the page
therefore cannot read a file, run a command, or reach a path of its own
choosing.

## State

`~/.aegisforge` is unchanged and compatibility-sensitive: the existing
database, node identity, workspace identity, conversations and drafts are
picked up as they are. The bundle carries no state and no model. New in this
execution:

- `~/.aegisforge/attachments/` — files selected for a request, each stored
  under its attachment id, never under a name taken from the file;
- `~/.aegisforge/desktop.lock` — the single-instance lock.

## Setup handoff

**Device role: macOS coordinator.** macOS 26.6.2, arm64, zsh; repository:
`/Users/adityatadge/Documents/GitHub/AegisForge`. Homebrew CPython **3.12.13** is
already installed at `/opt/homebrew/opt/python@3.12/bin/python3.12`.
The desktop uses a separate `desktop/.venv`; the existing coordinator `.venv`
and `~/.aegisforge` are not replaced.

The one-time command below installs new dependencies and opens the native app.
The requester approved it and it completed on this Mac on 2026-09-04; it does
not need repeating to open the app. Quit Refinix before rebuilding.

The reviewed package plan is in
[`requirements-macos.lock`](requirements-macos.lock), which includes
[`requirements-build-macos.lock`](requirements-build-macos.lock). It pins all
20 packages, their PyPI release metadata, artifact filenames, licences, sizes
and SHA-256 digests. Main versions: **pywebview 6.2.1**, **py2app 0.28.10**,
**PyObjC 12.2.2**, and **setuptools 80.9.0**, plus the existing backend's **Pydantic 2.13.5** pins. These are unmodified upstream
packages. Sources are `https://pypi.org/simple` and PyPI's
`https://files.pythonhosted.org` artifact host. Package metadata was checked
2026-09-04; observed startup on this Mac is recorded below. Other devices still
need their own acceptance check.

Artifact downloads total **12,495,337 bytes (12.5 MB)**. Reserve **1 GB** for the
virtual environment, package cache, build and app (an estimate, not a measured
bundle size); this Mac had 340 GiB free at preparation. `proxy-tools 0.1.0` is
source-only, so the script first installs the hash-pinned setuptools wheel,
then builds that small source package with build isolation disabled. The final
installation uses only the downloaded artifacts with `--no-index`; `pip check`
checks dependency consistency. No models, Ollama installer or Docker components
are downloaded. No signing identity, global package environment or host service
configuration is changed.

### Install, build and open once

For a future approved setup or rebuild, run in zsh:

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
./desktop/setup-macos.command
```

The same script can be double-clicked in Finder. It verifies macOS arm64 and
Python 3.12, installs the locked dependencies into `desktop/.venv`, builds a
standalone application, verifies its code signature, then opens:

`/Users/adityatadge/Documents/GitHub/AegisForge/desktop/dist/Refinix.app`

Opening Refinix may start an already-installed Ollama runtime when needed.
Ordinary Chat does not start Docker. If Ollama or the configured model is
missing, the app explains what is missing instead of downloading it.

### Open again

Double-click **Refinix.app** in `desktop/dist`, or run:

```bash
open /Users/adityatadge/Documents/GitHub/AegisForge/desktop/dist/Refinix.app
```

Once the window is open, right-click its Dock icon → **Options → Keep in Dock**.
You can then launch it from the Dock. For a source run after setup:

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
desktop/.venv/bin/python -m desktop
```

### Observed verification

On 2026-09-04, the approved setup completed on macOS 26.6.2 arm64 with CPython
3.12.13. All 20 downloaded artifacts matched their recorded SHA-256 hashes;
`pip check` and `codesign --verify --deep --strict` passed. The bundle opened
one native window and reported packaged mode, loopback binding and the existing
Ollama runtime reachable, without starting a second runtime.

The correction pass ran **161 Python checks and 8 Node checks**, then **7 final
lifecycle regressions** after adding the native Quit-during-startup repair.
They cover pre-header and stalled-stream cancellation, startup cleanup,
reused-coordinator shutdown, port metadata, Windows lock offsets and packaging.
A copied bundle started under a sandbox denying reads of the checkout and
Homebrew Python; the denied source read was separately confirmed. A second
launch reused the existing native instance, including after fallback to port
8771. No real model request was submitted during this pass.

The requester subsequently confirmed Chat → Stop → Command-Q → reopen with
the stopped conversation retained, and supplied a generated Kubernetes reply
from a follow-up request. The core macOS smoke test is requester-accepted;
these observations do not establish accuracy for every answer or other OS support.

The package stages only application Python sources plus the existing frontend;
it does not bundle the repository's environment or build output. Bytecode
optimization is disabled to avoid py2app 0.28.10's dangling `site.pyo` link.

### VERIFY — RUN THESE YOURSELF

**macOS coordinator:** the requester completed the core Chat/Stop/quit/history
check. For later builds, use these acceptance steps and record their outcomes:

1. Open from Finder: the symbol-only icon, Refinix application name, startup
   status and the existing Chat interface appear without a browser command.
2. Open again: it focuses the existing window, including after a port fallback.
3. Send a non-confidential test request. Stop both while waiting for the first
   response and during streaming; the request becomes stopped and can be retried.
4. Close while a request runs: cancellation is confirmed and recorded. Reopen:
   the same conversation history and drafts remain. Also close during startup.
The app is an **ad-hoc signed local build**. Developer ID signing, notarisation
and distribution are not configured. Other-device compatibility and zero-egress acceptance are not
claimed by the offline tests or by an idle connection snapshot.

### Rollback

Quit Refinix first. Remove only this setup's generated artifacts:

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
rm -rf desktop/.venv desktop/.packages desktop/build desktop/dist/Refinix.app
```

This preserves the existing coordinator environment, source, models, chat
history and `~/.aegisforge`. Remove the Dock shortcut separately if you added it.
Do not uninstall packages from the existing coordinator `.venv`.

## Other platform targets

The shared runtime declaration is
[`requirements-desktop.txt`](requirements-desktop.txt); it contains no
macOS-only packaging dependency. [pywebview's upstream packaging guide](https://pywebview.flowrl.com/guide/freezing.html)
uses py2app on macOS and PyInstaller on Windows/Linux.

**Windows:** shared shell code and `.ico` assets exist; byte-range locking has
an offline regression check. Windows runtime acceptance, WebView2/pythonnet
setup and a PyInstaller build configuration remain unfinished.

**Ubuntu:** shared shell code and hicolor PNG assets exist. GTK/WebKitGTK package
selection, runtime acceptance and a `.desktop` launcher remain unfinished.
No Ubuntu host action is part of this setup; C05 remains paused.

## GIT / GITHUB — RUN THESE YOURSELF

Repository: `/Users/adityatadge/Documents/GitHub/AegisForge`.
Observed `git status -sb`: `## aditya...origin/aditya`, with unstaged desktop
and C05 changes. No Git writes were performed. After accepting the app, review
the diff and select only Execution 1 hunks in the shared documentation/ledgers;
leave C05 pending. The explicit paths below include the original desktop work
and these corrections. Generated environments, caches and app binaries stay ignored.

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
git status -sb
git diff
git add -p -- .gitignore README.md tasks.md agent-memory/userprompts.md agent-memory/agentchangelog.md
git add -- desktop/README.md desktop/__init__.py desktop/__main__.py desktop/refinix.py desktop/lifecycle.py desktop/shell.py desktop/setup_py2app.py desktop/setup-macos.command desktop/requirements-desktop.txt desktop/requirements-build-macos.lock desktop/requirements-macos.lock desktop/test_lifecycle.py desktop/test_packaging.py desktop/test_review_fixes.py desktop/icons/
git add -- backend/coordinator/README.md backend/coordinator/__init__.py backend/coordinator/db.py backend/coordinator/runtime.py backend/coordinator/server.py backend/coordinator/test_coordinator.py backend/coordinator/test_desktop_surface.py
git add -- frontend/app/app.js frontend/app/control.html frontend/app/fixture.html frontend/app/index.html frontend/app/test-conversations.cjs frontend/app/code.html frontend/app/refinix.css frontend/app/assets/refinix-mark.png frontend/app/assets/refinix-wordmark.png frontend/design/assets/Brand/refinix-logo-horizontal.jpeg frontend/design/assets/Brand/refinix-logo-stacked.jpeg scripts/build-brand-assets.py
git diff --cached
git commit -m "feat(desktop): add and verify Refinix macOS foundation"
```
