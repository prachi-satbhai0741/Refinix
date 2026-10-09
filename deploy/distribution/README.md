# Website and Beta update feed — the distribution repository

`refinix.runs-on.dev` is served by GitHub Pages from the website repository
(`vedantsur09/refinix-site`). From Refinix Beta 0.1 on, that one repository serves the
website **and** the Beta update feed (`/updates/beta/`), from one committed tree, so the site and
the feed can never disagree. Release assets themselves are GitHub releases of the source
repository (`prachi-satbhai0741/Refinix`).

The workflow files here are templates kept with the source so they are reviewed with it; the
website repository's owner copies them into that repository's `.github/workflows/`.

| Template | Runs | Does |
|---|---|---|
| [`deploy-site.yml`](workflows/deploy-site.yml) | a person's push to `main`, or by hand | deploys the head of `main` to Pages; skips if `main` moved (a newer run deploys) |
| [`advance-feed.yml`](workflows/advance-feed.yml) | by hand, after a required reviewer approves | checks the staged targets, downloads each new release asset anonymously and checks its size, SHA-256 and final download host, signs snapshot + timestamp, commits, deploys exactly that commit, then passes only when the live feed, page, `release.json` and every download are exactly that commit's (`update_repository.py expected` → `verify --expect`, `scripts/verify_public.py`) |
| [`refresh-feed.yml`](workflows/refresh-feed.yml) | daily and by hand | re-signs the timestamp (and a low snapshot), commits, deploys, passes only when the live feed is exactly the new commit's and fresh, opens an issue when something fails or expiry is near |

All three share the `beta-feed` queue. See [`docs/releases.md`](../../docs/releases.md#beta-channel)
for the rules (immutable files, forward-only versions, fix forward, key custody).

## One-time setup by the website repository's owner

Settings → Pages:

1. **Source: GitHub Actions** (instead of "Deploy from a branch"). The custom domain stays
   `refinix.runs-on.dev` with HTTPS enforced.

Settings → Environments:

2. `github-pages` — deployment branches: `main` only.
3. `beta-publish` — deployment branches: `main` only; **required reviewer**: the release manager.
   Secrets: `REFINIX_SNAPSHOT_KEY`, `REFINIX_TIMESTAMP_KEY` (the encrypted PEM text of the online
   keys) and `REFINIX_KEY_PASSPHRASE_SNAPSHOT`, `REFINIX_KEY_PASSPHRASE_TIMESTAMP`.
4. `beta-feed-refresh` — deployment branches: `main` only; no reviewer (so the schedule runs);
   the same four secrets.

Settings → Secrets and variables → Actions → Variables:

5. `REFINIX_TOOLING_COMMIT` — the full commit SHA of the source repository whose
   `scripts/update_repository.py` the feed workflows run. Change it only to a reviewed `main` commit.

Never add these keys as repository-level secrets: any workflow on any branch could read them.

Repository content:

6. Copy the three workflow files into `.github/workflows/`.
7. Commit `updates/beta/metadata/1.root.json` (from the release manager's offline `init`) and
   `updates/beta/targets/` as the feed starts; the site exporter
   (`scripts/build-site.sh` in the source repository) writes the website files and `release.json`.

## The source repository's settings (its owner)

- Settings → General → Releases: **enable release immutability**.
- Settings → Environments → `beta-sign` (only when Windows signing exists): deployment branch
  `main`, required reviewer, secret `REFINIX_WINDOWS_SIGN_COMMAND` (a signtool command line with
  `{file}`), variable `REFINIX_WINDOWS_PUBLISHER` (the certificate subject).
- About: description, website `https://refinix.runs-on.dev`, topics, social preview — see the
  release checklist in the current release's `PUBLISH-COMMANDS.md`.
