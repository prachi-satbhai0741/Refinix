# Contributing to AegisForge

This document is the branch, review, and ownership workflow required by
[`prd.md`](prd.md) section 17.3.

## The one rule

```
  your branch  ──PR──>  dev  ──PR──>  main
```

**Nobody pushes to `main`. Nobody pushes to `dev`.** Not the repo owner, not
in an emergency, not "just this once". Both branches accept commits only
through a pull request.

That is the *only* hard rule. Everything else is open: anyone may open a PR,
anyone may review one, anyone may merge one — including their own — as soon
as the checks are green. No approval quota, no owner sign-off, no waiting on
a specific person. The gate is the pull request and its checks, not
permission from a human.

## One-time setup

Clone, then install the local hooks:

```bash
git clone https://github.com/prachi-satbhai0741/AegisForge.git
cd AegisForge
./scripts/install-hooks.sh
```

That installs a `pre-push` hook that stops a stray `git push origin main`
on your own machine, with a message telling you what to do instead. The
server rejects it anyway; the hook just saves you the round trip.

Check it worked — this command **should fail**:

```bash
git push --dry-run origin HEAD:main
```

## Branches

| Branch | Owner | Purpose |
|---|---|---|
| `main` | protected | Release. Only ever receives a PR from `dev`. |
| `dev` | protected | Integration. Receives PRs from member branches. |
| `aditya` | @adityatadge31 | Personal work branch |
| `prachi` | @prachi-satbhai0741 | Personal work branch |
| `sahil` | @sahilranade45 | Personal work branch |
| `tanvi` | @tanvishinde3010 | Personal work branch |
| `vedant` | @vedantsur09 | Personal work branch |
| `yug` | @Yugu-48 | Personal work branch |

Work on your own branch. If you have several things in flight, open topic
branches underneath your name — `aditya/coordinator-api`, `yug/ocr-worker`.
Both the bare name and the `name/topic` form are accepted into `dev`.

Do not push to someone else's branch. Open a PR against it if you need to
contribute there.

## Daily flow

```bash
# 1. Start from the latest dev
git switch dev && git pull
git switch -c <your-name>/<topic>     # or: git switch <your-name>

# 2. Work, commit
git add -p
git commit -m "coordinator: add capability registry"

# 3. Push your branch
git push -u origin <your-name>/<topic>

# 4. Open a PR into dev
gh pr create --base dev --fill
```

Fill in the PR template properly. The evidence and safety sections are not
decoration — see "Review" below.

## Releasing to `main`

Only `dev` opens a PR into `main`. Any other source branch fails the
`pr-flow-guard` check and cannot be merged.

```bash
gh pr create --base main --head dev --title "Release: <what is in it>"
```

`main` merges use a **merge commit**, never a squash — a squash would rewrite
the commits and leave `dev` permanently diverged from `main`. PRs into `dev`
may be squashed.

## Merging

A PR merges when its **checks are green**. That is the whole gate — no
approving review is required, and you may merge your own PR.

[`.github/CODEOWNERS`](.github/CODEOWNERS) will auto-request a review on
security, protocol, model-catalogue, licensing and governance paths. That is
a heads-up, not a blocker; it never stops a merge.

Work on `dev` until it is genuinely ready, then take it to `main` in one PR.
Anyone can open and merge that release PR.

Reviewing is still worth doing. When you do, check:

- **Evidence.** PRD 17.3: decisions are evidence-backed and dated. A claim
  with no command output, timing, or test run behind it is not ready.
- **Honest labels.** PRD 17.3: features are labelled planned, prototyped,
  verified, or deferred. "Prototyped" presented as "verified" is a bug.
- **No mocked paths sold as real.** PRD 21 Day 2 exit evidence: "No mocked
  inference in the claimed path."
- **AI output was actually read.** PRD 17.3: do not merge generated output
  nobody has reviewed.
- **Nothing forbidden was committed.** See below.

## Never commit

From PRD 15.3:

- Model weights
- Generated installers or release binaries
- Signing keys or tokens
- Private documents
- Real confidential scans
- Local chat databases
- Environment files containing secrets

Use synthetic or explicitly approved non-sensitive test fixtures.

## Enforcement

Three layers, weakest to strongest:

| Layer | What it does | Can it be bypassed? |
|---|---|---|
| [`.githooks/pre-push`](.githooks/pre-push) | Blocks direct pushes to `main`/`dev` locally | Yes — `--no-verify`, or a clone that never ran the installer |
| [`no-direct-push.yml`](.github/workflows/no-direct-push.yml) | Fails loudly if a commit lands without a PR | It reports after the fact; it cannot prevent |
| Branch ruleset | Server-side rejection | No. `bypass_actors` is empty, so admins are included |

The ruleset requires a PR and passing checks. It does **not** require
approvals — `required_approving_review_count` is `0` by design.

The ruleset is applied by
[`scripts/setup-branch-protection.sh`](scripts/setup-branch-protection.sh) and
requires **repository admin**. If `no-direct-push` ever fails, protection is
missing — tell @prachi-satbhai0741.

### Adding a build or test gate

Right now the only required check is `pr-flow-guard`. As real build, test and
lint jobs land, add their **job names** to the required list so `dev` cannot
go to `main` until they pass:

```bash
REQUIRED_CHECKS="pr-flow-guard build test lint" ./scripts/setup-branch-protection.sh
```

The name must match the workflow's `jobs.<id>.name` and that job must run on
`pull_request` for the branch, or the PR waits forever on a check that never
reports.

### Why pr-flow-guard exists

The `pr-flow-guard` check enforces the *direction* of the flow. GitHub
rulesets can require a pull request but cannot restrict which branch it comes
from, so [`pr-flow-guard.yml`](.github/workflows/pr-flow-guard.yml) does that
part and is registered as a required check on both `main` and `dev`.

## Emergency changes

There is no bypass path by design. If `main` is genuinely broken:

1. Say so in the team channel first.
2. An admin sets the `aegisforge-main` ruleset to **Disabled** in
   Settings → Rules → Rulesets.
3. Make the fix.
4. Re-enable the ruleset immediately.

Do not add a permanent bypass actor.

## Adding or removing a team member

Three files must change together:

1. `MEMBERS` in [`.github/workflows/pr-flow-guard.yml`](.github/workflows/pr-flow-guard.yml)
2. The branch table above
3. [`.github/CODEOWNERS`](.github/CODEOWNERS) if they own reviewed paths

The change lands like any other: PR into `dev`, then `dev` into `main`.
