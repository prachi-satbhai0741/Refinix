#!/usr/bin/env bash
set -euo pipefail

read -r -a packages <<< "$PACKAGES"
for package in "${packages[@]}"; do
  [[ "$package" =~ ^[a-z0-9][a-z0-9.+:-]*$ ]] || { echo "Invalid package: $package"; exit 1; }
done
[ "${#packages[@]}" -gt 0 ]
options=(-o Acquire::Retries=2 -o Acquire::http::Timeout=30
         -o Acquire::https::Timeout=30 -o APT::Update::Error-Mode=any)

if ! timeout --kill-after=10s 180s sudo apt-get "${options[@]}" update; then
  echo "::warning::APT update failed or timed out; retrying with official Ubuntu mirrors"
  # Change only Ubuntu transport URIs on this disposable runner. Keep suites,
  # components and Signed-By, so repository authentication is unchanged.
  sudo python3 - <<'PY'
from pathlib import Path
for name, uri in (("apt-mirrors.txt", "https://archive.ubuntu.com/ubuntu"),
                  ("apt-security-mirrors.txt", "https://security.ubuntu.com/ubuntu")):
    path = Path("/etc/apt") / name
    if path.is_file():
        path.write_text(uri + "\n")
for path in (Path("/etc/apt/sources.list"),
             Path("/etc/apt/sources.list.d/ubuntu.sources")):
    if path.is_file():
        text = path.read_text()
        path.write_text(text.replace("http://azure.archive.ubuntu.com/ubuntu",
                                     "https://archive.ubuntu.com/ubuntu")
                            .replace("https://azure.archive.ubuntu.com/ubuntu",
                                     "https://archive.ubuntu.com/ubuntu"))
PY
  timeout --kill-after=10s 180s sudo apt-get "${options[@]}" update
fi
timeout --kill-after=10s 600s sudo env DEBIAN_FRONTEND=noninteractive \
  apt-get "${options[@]}" install -y --no-install-recommends "${packages[@]}"
